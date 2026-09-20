"""出版指纹闸门：三格式成品的一致性与分页质检（阶段八，视觉验收前置）。

拦截两类真实事故（第 7 期实证）：
    1. 「已生成实为旧文件」——无头浏览器 rc=0 但未写目标，旧 PDF 被静默放行；
       用内容指纹（md 关键零件在 HTML 与 PDF 文本层均命中）+ mtime 链拦截。
    2. 分页孤行——条目出处行孤立页首、报尾标题与正文分离、空白页。

用法（pymupdf 为临时依赖，不落环境）:
    uv run --with pymupdf python scripts/verify_release.py issues/<dirname>
    uv run --with pymupdf python scripts/verify_release.py issues/<dirname> --render _render

退出码：0 = 全部通过；1 = 存在问题（视觉验收前必须修复）。
"""

import argparse
import glob
import os
import re
import sys

try:
    import pymupdf
except ImportError:  # pragma: no cover
    print("错误: 缺少 pymupdf。请用 `uv run --with pymupdf python` 运行本脚本。",
          file=sys.stderr)
    sys.exit(2)


def _fingerprint(s):
    """指纹归一化：只保留中文/字母/数字——消除断行、空白、标点与 HTML 转义差异。"""
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", s)


def _sole(glob_pat, dirname):
    hits = [f for f in glob.glob(os.path.join(dirname, glob_pat)) if os.path.isfile(f)]
    return hits[0] if len(hits) == 1 else None


def collect_md_fingerprints(md_path):
    """从成品 md 提取内容指纹：H1 / 刊号 / 发刊 / 导读首句 / 头条标题 / AI 说明句。"""
    with open(md_path, "r", encoding="utf-8") as f:
        lines = [l.rstrip("\n") for l in f]
    fps = []
    h1 = next((l for l in lines if l.startswith("# ")), None)
    if h1:
        # H1 在 HTML 报头被拆成「刊名」与「期号·区间」两个组件，各成独立指纹
        m = re.match(r"^(.*?)第\s*\d+\s*期(.*)$", h1[2:].strip())
        if m:
            fps.append(("H1 刊名", m.group(1).strip()))
            fps.append(("H1 期号区间", "第 {} 期{}".format(
                re.search(r"第\s*(\d+)\s*期", h1).group(1), m.group(2))))
        else:
            fps.append(("H1 刊头", h1[2:].strip()))
    pub = next((l for l in lines if l.startswith("刊号")), None)
    if pub:
        fps.append(("刊号行", pub.strip()))
    date = next((l for l in lines if l.startswith("发刊")), None)
    if date:
        fps.append(("发刊电头", date.strip()))
    head = next((l for l in lines if l.startswith("## ")), None)
    if head:
        fps.append(("头条标题", head[3:].strip()))
    # 导读首句：H1 与首个 H2 之间的首个非零件正文行，取首句（到首个句号）
    first_h2 = next((i for i, l in enumerate(lines) if l.startswith("## ")), len(lines))
    for l in lines[1:first_h2]:
        s = l.strip()
        if s and not s.startswith(("#", "刊号", "开源仓库", "发刊")):
            fps.append(("导读首句", s.split("。")[0][:24]))
            break
    for i, l in enumerate(lines):
        if l.strip().startswith("**AI 撰写说明"):
            body = "".join(x.strip() for x in lines[i + 1:i + 3])
            m = re.search(r"本文由.{0,24}", body)
            if m:
                fps.append(("AI 说明句", m.group(0)))
            break
    return [(name, _fingerprint(text)) for name, text in fps if _fingerprint(text)]


def check_pagination(pdf_path, problems):
    doc = pymupdf.open(pdf_path)
    for i, page in enumerate(doc):
        lines = [l.strip() for l in page.get_text().strip().splitlines() if l.strip()]
        if not lines:
            problems.append("分页: 第 {} 页是空白页".format(i + 1))
            continue
        if lines[0].startswith("出处"):
            problems.append("分页: 第 {} 页首行是孤立出处行（条目被跨页拆断）: {}"
                            .format(i + 1, lines[0][:30]))
        if lines[-1] == "AI 撰写说明":
            problems.append("分页: 第 {} 页末行是 AI 撰写说明标题（报尾被跨页拆断）"
                            .format(i + 1))
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser(description="周报三格式出版指纹闸门")
    ap.add_argument("dirname", help="期目录，如 issues/CS26-0903-TP")
    ap.add_argument("--render", default=None, metavar="DIR",
                    help="额外把 PDF 全部页面渲染为 PNG 到该目录（供视觉验收）")
    args = ap.parse_args(argv)

    dirname = args.dirname
    problems = []
    md = _sole("CSSEC*.md", dirname)
    html = _sole("CSSEC*.html", dirname)
    pdf = _sole("CSSEC*.pdf", dirname)
    for label, path in (("md", md), ("html", html), ("pdf", pdf)):
        if path is None:
            problems.append("三格式: {} 缺失或不止一份（目录 {}）".format(label, dirname))
    if problems:
        for p in problems:
            print("[FAIL] {}".format(p))
        return 1
    for label, path in (("html", html), ("pdf", pdf)):
        if os.path.getsize(path) == 0:
            problems.append("三格式: {} 为空文件".format(label))
        if os.path.getmtime(path) < os.path.getmtime(md) - 2:
            problems.append(
                "mtime: {} 旧于 md（产物疑似过期，重跑 md2html/html2pdf）: {}".format(
                    label, os.path.basename(path)))

    # 内容指纹：md 关键零件须在 HTML 源码与 PDF 文本层同时命中
    # （HTML 侧先去标签：报头/AI 说明句里零件值被 span 等标记包裹）
    fps = collect_md_fingerprints(md)
    html_text = re.sub(r"<[^>]+>", "", open(html, "r", encoding="utf-8").read())
    html_norm = _fingerprint(html_text)
    doc = pymupdf.open(pdf)
    pdf_norm = _fingerprint("".join(p.get_text() for p in doc))
    for name, fp in fps:
        if fp and fp not in html_norm:
            problems.append("指纹: 「{}」未在 HTML 中命中（HTML 与 md 不一致）".format(name))
        if fp and fp not in pdf_norm:
            problems.append("指纹: 「{}」未在 PDF 中命中（PDF 疑为旧文件，重跑出版）".format(name))

    check_pagination(pdf, problems)
    pages = doc.page_count
    doc.close()

    if problems:
        for p in problems:
            print("[FAIL] {}".format(p))
        print("结论: 未通过（{} 项问题，共 {} 页）".format(len(problems), pages))
        return 1

    if args.render:
        os.makedirs(args.render, exist_ok=True)
        doc = pymupdf.open(pdf)
        for i, page in enumerate(doc):
            page.get_pixmap(dpi=70).save(
                os.path.join(args.render, "p{:02d}.png".format(i + 1)))
        doc.close()
        print("已渲染 {} 页到 {}".format(pages, args.render))
    print("结论: 通过（三格式指纹一致，{} 页分页无孤行）".format(pages))
    return 0


if __name__ == "__main__":
    sys.exit(main())
