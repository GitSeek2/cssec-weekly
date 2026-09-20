"""周报 HTML → PDF 转换器。

把 `scripts/md2html.py` 生成的单文件 HTML（周报.html）用无头浏览器打印成 PDF
（周报.pdf）。走浏览器的打印管线，因此自动应用 HTML 内嵌的 `@media print`
样式与 `@page{margin:18mm 16mm}`——这也是 HTML 版式里 print 样式存在的意义。

做的事：
    1. 定位本机无头浏览器：候选路径覆盖 Windows（Edge/Chrome，Win11 自带
       Edge）、macOS 与 Linux 常见安装位置，再到 PATH；按优先序逐候选回退
       （首个打印失败自动试下一个）；可用 CSSEC_PDF_BROWSER 环境变量或
       --browser 显式指定。
    2. 用 `--headless --print-to-pdf`（附 `--no-pdf-header-footer`，去掉默认
       页眉页脚）把 HTML 渲染成 PDF；先打印到 ASCII 临时路径再移动覆盖，
       防浏览器对非 ASCII 目标路径的静默不写。
    3. 校验产物存在且非空。
    4. 目录大纲注入（可选）：Chromium 打印不产书签，打印成功后从同目录
       同名 md 的 H1/H2/H3 用 pymupdf 补写 outline（H2=1 级、H3=2 级），
       阅读器侧边栏可解析。装了 pymupdf 自动生效（uv run --with pymupdf），
       未装则跳过不失败。

用法:
    uv run --with pymupdf python scripts/html2pdf.py <周报.html>
    uv run python scripts/html2pdf.py 周报.html -o 周报.pdf

输出:
    - 默认：输入同目录、同名 .pdf（周报.html → 周报.pdf），成功打印一行
      「已生成: <绝对路径>」。
    - 失败：stderr 打印错误，exit 1。

零外部依赖（仅标准库 + 本机浏览器）。PDF 渲染取决于浏览器版本与字体，
不完全逐字节确定（HTML 阶段 md2html.py 仍完全确定）。
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 常见浏览器路径（按优先级；Edge 是 Win11 自带，用户级 Chrome 覆盖仅装到
# %LOCALAPPDATA% 的常见情形，后三条覆盖 macOS / Linux）
_BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    r"%LOCALAPPDATA%\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
]
_BROWSER_NAMES = ("msedge", "edge", "chrome", "google-chrome", "chromium")


def find_browsers(explicit=None):
    """按优先序返回可用浏览器候选列表：--browser > 环境变量 > 常见路径 > PATH。

    返回列表而非单个路径——首个浏览器打印失败（如 Edge 更新中间态
    rc=0 不产文件）时由 main 逐个回退尝试下一个。"""
    if explicit:
        if os.path.isfile(explicit):
            return [explicit]
        raise FileNotFoundError("--browser 指定的路径不存在: {}".format(explicit))
    found = []
    env = os.environ.get("CSSEC_PDF_BROWSER")
    if env and os.path.isfile(env):
        found.append(env)
    for cand in _BROWSER_CANDIDATES:
        cand = os.path.expandvars(cand)
        if os.path.isfile(cand) and cand not in found:
            found.append(cand)
    for name in _BROWSER_NAMES:
        p = shutil.which(name)
        if p and p not in found:
            found.append(p)
    if not found:
        raise FileNotFoundError(
            "未找到可用的无头浏览器（Edge/Chrome）。请安装 Edge，或用 "
            "CSSEC_PDF_BROWSER 环境变量 / --browser 指定浏览器可执行文件路径。")
    return found


def print_to_pdf(browser, html_path, pdf_path, timeout=180):
    """headless 打印 HTML → PDF；返回 (ok, stderr_tail)。

    Edge 对含非 ASCII 字符的 --print-to-pdf 目标路径偶发静默不写（进程退出码 0
    但目标未被更新，旧文件原样留存），因此先打印到 ASCII 临时路径，成功后再
    移动覆盖目标——避免"已生成"实际是旧版的静默失败。"""
    url = Path(html_path).resolve().as_uri()
    tmp = tempfile.mkdtemp(prefix="cssec_pdf_")
    tmp_pdf = os.path.join(tmp, "out.pdf")
    base = [
        browser,
        "--disable-gpu",
        "--no-first-run",
        "--disable-extensions",
        "--disable-background-networking",
        "--no-pdf-header-footer",
        "--user-data-dir=" + tmp,
        "--print-to-pdf=" + tmp_pdf,
        url,
    ]
    ok = False
    # 老版本不认 --headless=new，退回 --headless
    for headless in ("--headless=new", "--headless"):
        try:
            proc = subprocess.run(base + [headless], capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            break
        if proc.returncode == 0 and os.path.isfile(tmp_pdf) and os.path.getsize(tmp_pdf) > 0:
            ok = True
            break
    if ok:
        shutil.move(tmp_pdf, pdf_path)
        shutil.rmtree(tmp, ignore_errors=True)
        return True, ""
    shutil.rmtree(tmp, ignore_errors=True)
    tail = (proc.stderr or "").strip().splitlines()[-3:] if proc else []
    return False, "浏览器退出码 {}：{}".format(
        proc.returncode if proc else -1, " | ".join(tail) if tail else "无 stderr 输出")


def _default_output(path):
    base, _ = os.path.splitext(path)
    return base + ".pdf"


def _fingerprint(s):
    """大纲页定位用的归一化：只留中文/字母/数字（与 verify_release 一致）。"""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s)


def inject_outline(html_path, pdf_path):
    """从同目录同名 md 的 H1/H2/H3 生成 PDF 目录大纲（阅读器侧边栏可解析）。

    Chromium 的 --print-to-pdf 不产书签，打印后用 pymupdf 补写：
    H2（本期主题/板块）为 1 级、H3（条目）为 2 级、刊头为首个 1 级；
    页码按标题指纹在 PDF 文本层单调搜索定位。pymupdf 为可选依赖——
    未安装时跳过并提示（不失败），用 `uv run --with pymupdf` 运行即启用。
    返回 (注入条数 or None)。
    """
    try:
        import pymupdf
    except ImportError:
        print("提示: 未装 pymupdf，跳过目录大纲注入"
              "（如需大纲：uv run --with pymupdf 运行本脚本）")
        return None

    md_path = os.path.splitext(html_path)[0] + ".md"
    if not os.path.isfile(md_path):
        print("提示: 未找到同名 md（{}），跳过目录大纲注入".format(md_path))
        return None

    headings, issue_no = [], None
    with open(md_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if issue_no is None and s.startswith("# "):
                m = re.search(r"第\s*(\d+)\s*期", s)
                issue_no = m.group(1) if m else ""
            elif s.startswith("## ") and not s.startswith("### "):
                headings.append((1, s[3:].strip()))
            elif s.startswith("### "):
                headings.append((2, s[4:].strip()))
    if not headings:
        return 0

    doc = pymupdf.open(pdf_path)
    page_fps = [_fingerprint(p.get_text()) for p in doc]
    toc = [[1, "CSSEC 周报 第 {} 期".format(issue_no) if issue_no else "CSSEC 周报", 1]]
    cur_page = 0  # 标题按文档顺序单调出现，从上一命中页起向后找
    dropped = []
    for level, title in headings:
        fp = _fingerprint(title)
        if not fp:
            continue
        hit = next((i for i in range(cur_page, doc.page_count) if fp in page_fps[i]), None)
        if hit is None:
            dropped.append(title[:20])
            continue
        cur_page = hit
        toc.append([level, title, hit + 1])
    doc.set_toc(toc)
    # 全量保存到 ASCII 临时路径再替换（saveIncr 增量更新在个别阅读器上
    # 大纲渲染不稳，全量重写彻底消除该变量；deflate 压缩控制体积）
    tmp_pdf = os.path.join(tempfile.mkdtemp(prefix="cssec_toc_"), "out.pdf")
    doc.save(tmp_pdf, garbage=3, deflate=True)
    doc.close()
    shutil.move(tmp_pdf, pdf_path)
    if dropped:
        print("提示: {} 个标题未在 PDF 定位到，未进大纲: {}".format(
            len(dropped), " / ".join(dropped)))
    return len(toc)


def main(argv=None):
    ap = argparse.ArgumentParser(description="周报 HTML → PDF（无头浏览器打印）")
    ap.add_argument("input", help="输入 HTML 文件路径（md2html.py 产物）")
    ap.add_argument("-o", "--output", default=None,
                    help="输出 PDF 路径（默认：输入同目录同名 .pdf）")
    ap.add_argument("--browser", default=None,
                    help="浏览器可执行文件路径（默认自动探测 Edge/Chrome）")
    args = ap.parse_args(argv)

    try:
        html_path = os.path.abspath(args.input)
        if not os.path.isfile(html_path):
            raise FileNotFoundError("输入文件不存在: {}".format(html_path))
        pdf_path = os.path.abspath(args.output or _default_output(args.input))
        parent = os.path.dirname(pdf_path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        candidates = find_browsers(args.browser)
        ok, last_err, tried = False, "", []
        for browser in candidates:
            tried.append(browser)
            ok, last_err = print_to_pdf(browser, html_path, pdf_path)
            if ok:
                break
        if not ok:
            raise RuntimeError(
                "全部 {} 个浏览器候选打印失败（{}）：{}".format(
                    len(tried), " | ".join(tried), last_err))
        if not (os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0):
            raise RuntimeError("产物缺失或为空: {}".format(pdf_path))

        n_outline = inject_outline(html_path, pdf_path)
        print("已生成: {}".format(pdf_path))
        if n_outline:
            print("目录大纲: {} 条（阅读器侧边栏可解析）".format(n_outline))
        return 0
    except Exception as e:  # noqa: BLE001
        print("错误: {}".format(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
