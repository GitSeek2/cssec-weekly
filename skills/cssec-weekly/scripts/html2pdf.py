"""周报 HTML → PDF 转换器。

把 `scripts/md2html.py` 生成的单文件 HTML（周报.html）用无头浏览器打印成 PDF
（周报.pdf）。走浏览器的打印管线，因此自动应用 HTML 内嵌的 `@media print`
样式与 `@page{margin:18mm 16mm}`——这也是 HTML 版式里 print 样式存在的意义。

做的事：
    1. 定位本机无头浏览器：优先 Edge（Windows 11 自带，路径固定），
       其次 Chrome，再到 PATH；可用 `CSSEC_PDF_BROWSER` 环境变量或 `--browser`
       显式指定。
    2. 用 `--headless --print-to-pdf`（附 `--no-pdf-header-footer`，去掉默认
       页眉页脚）把 HTML 渲染成 PDF。
    3. 校验产物存在且非空。

用法:
    uv run python scripts/html2pdf.py ../../issues/CS26-0801-TP/CSSEC 周报 · 第 1 期.html
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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# 常见浏览器路径（按优先级；Edge 是 Win11 自带）
_BROWSER_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
_BROWSER_NAMES = ("msedge", "edge", "chrome", "google-chrome", "chromium")


def find_browser(explicit=None):
    """定位无头浏览器路径：--browser > 环境变量 > 常见路径 > PATH。"""
    if explicit:
        if os.path.isfile(explicit):
            return explicit
        raise FileNotFoundError("--browser 指定的路径不存在: {}".format(explicit))
    env = os.environ.get("CSSEC_PDF_BROWSER")
    if env and os.path.isfile(env):
        return env
    for cand in _BROWSER_CANDIDATES:
        if os.path.isfile(cand):
            return cand
    for name in _BROWSER_NAMES:
        p = shutil.which(name)
        if p:
            return p
    raise FileNotFoundError(
        "未找到可用的无头浏览器（Edge/Chrome）。请安装 Edge，或用 "
        "CSSEC_PDF_BROWSER 环境变量 / --browser 指定浏览器可执行文件路径。")


def print_to_pdf(browser, html_path, pdf_path, timeout=180):
    """headless 打印 HTML → PDF；返回 (ok, stderr_tail)。"""
    url = Path(html_path).resolve().as_uri()
    tmp = tempfile.mkdtemp(prefix="cssec_pdf_")
    base = [
        browser,
        "--disable-gpu",
        "--no-first-run",
        "--disable-extensions",
        "--disable-background-networking",
        "--no-pdf-header-footer",
        "--user-data-dir=" + tmp,
        "--print-to-pdf=" + pdf_path,
        url,
    ]
    # 老版本不认 --headless=new，退回 --headless
    for headless in ("--headless=new", "--headless"):
        try:
            proc = subprocess.run(base + [headless], capture_output=True,
                                  text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            shutil.rmtree(tmp, ignore_errors=True)
            return False, "打印超时（{}s）".format(timeout)
        if proc.returncode == 0:
            shutil.rmtree(tmp, ignore_errors=True)
            return True, ""
    shutil.rmtree(tmp, ignore_errors=True)
    tail = (proc.stderr or "").strip().splitlines()[-3:]
    return False, "浏览器退出码 {}：{}".format(
        proc.returncode, " | ".join(tail) if tail else "无 stderr 输出")


def _default_output(path):
    base, _ = os.path.splitext(path)
    return base + ".pdf"


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

        browser = find_browser(args.browser)
        ok, err = print_to_pdf(browser, html_path, pdf_path)
        if not ok:
            raise RuntimeError(err)
        if not (os.path.isfile(pdf_path) and os.path.getsize(pdf_path) > 0):
            raise RuntimeError("产物缺失或为空: {}".format(pdf_path))

        print("已生成: {}".format(pdf_path))
        return 0
    except Exception as e:  # noqa: BLE001
        print("错误: {}".format(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
