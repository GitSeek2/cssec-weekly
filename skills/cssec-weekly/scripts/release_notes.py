"""发刊 Release Note 生成器（供发刊 CI 使用）。

供 GitHub Actions 发刊工作流（.github/workflows/release.yml）使用：git tag 即期
目录刊号（如 CS26-0801-TP），据此定位 issues/<刊号>/，校验 md/html/pdf 三件套
齐全，再从 HISTORY.md 解析该期「刊号 / 发刊日期 / 头条」，在 stdout 输出
Release Note Markdown（工作流把它重定向为 Release 的 body）。

用法:
    uv run python scripts/release_notes.py --dirname CS26-0801-TP
    uv run python scripts/release_notes.py --dirname CS26-0801-TP --issue-only  # 只打期号

默认输出（stdout）:
    # CSSEC 周报 第 1 期
    - 刊号：CS26-0801-TP
    - 发刊：2026-08-09
    - 头条：AI 安全测试失控，三巨头接连越界
    附：本 Release 含 md / html / pdf 三份成品与 sources/ 中间稿。

失败时向 stderr 报错并退出 1；HISTORY 缺该期条目时提示先跑 append_history.py。
"""

import argparse
import os
import re
import sys

# 仓库根 = 脚本目录向上四级（<根>/skills/cssec-weekly/scripts/…）。
_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
ISSUES_DIR = os.path.join(_ROOT, "issues")
HISTORY = os.path.join(_ROOT, "HISTORY.md")

_ISSUE = re.compile(r"第\s*([0-9]+)\s*期", re.UNICODE)
_SECTION = re.compile(r"^##\s*第\s*([0-9]+)\s*期", re.UNICODE)
_FIELD = re.compile(r"^[-*]\s*(刊号|头条)\s*[:：]\s*(.+)$", re.UNICODE)
_DATE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")


def die(msg):
    print(f"错误：{msg}", file=sys.stderr)
    sys.exit(1)


def issue_number(dirpath):
    """从期目录内成品文件名取期号（int）；目录不存在或未找到则返回 None。"""
    if not os.path.isdir(dirpath):
        return None
    for name in os.listdir(dirpath):
        m = _ISSUE.search(name)
        if m:
            return int(m.group(1))
    return None


def check_artifacts(dirpath):
    """返回缺失的成品扩展名列表（md/html/pdf 缺哪个列哪个）。"""
    missing = []
    for ext in (".md", ".html", ".pdf"):
        found = any(f.endswith(ext) and _ISSUE.search(f)
                    for f in os.listdir(dirpath))
        if not found:
            missing.append(ext)
    return missing


def parse_history(path):
    """解析 HISTORY.md → {期号: {"date": "YYYY-MM-DD", "kanhao": str, "headline": str}}。

    小节格式（由 append_history.py 统一追加）：
        ## 第 N 期（YYYY-MM-DD 发刊）
        - 刊号：CS26-0801-TP
        - 头条：……
    """
    entries = {}
    if not os.path.isfile(path):
        return entries
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    cur = None
    for ln in lines:
        sm = _SECTION.match(ln)
        if sm:
            cur = int(sm.group(1))
            date = ""
            m = _DATE.search(ln)
            if m:
                date = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
            entries.setdefault(cur, {"date": date, "kanhao": "", "headline": ""})
            continue
        if cur is None:
            continue
        fm = _FIELD.match(ln)
        if fm:
            key, val = fm.group(1), fm.group(2).strip()
            if key == "刊号":
                entries[cur]["kanhao"] = val
            elif key == "头条":
                entries[cur]["headline"] = val
    return entries


def main():
    ap = argparse.ArgumentParser(description="从 HISTORY.md 生成某期发刊 Release Note")
    ap.add_argument("--dirname", required=True,
                    help="期目录刊号（= git tag，如 CS26-0801-TP）")
    ap.add_argument("--issues-dir", default=ISSUES_DIR, help="成品存档目录（默认仓库根 issues/）")
    ap.add_argument("--history", default=HISTORY, help="HISTORY.md 路径（默认仓库根）")
    ap.add_argument("--issue-only", action="store_true",
                    help="只打印期号数字（供 workflow 拼 Release 标题），不打印 Note")
    args = ap.parse_args()

    dirpath = os.path.join(args.issues_dir, args.dirname)
    n = issue_number(dirpath)
    if n is None:
        die(f"目录 {dirpath} 中未找到含「第 N 期」的成品文件")
    missing = check_artifacts(dirpath)
    if missing:
        die(f"目录 {dirpath} 缺少成品：{', '.join(missing)}（应先跑 md2html.py / html2pdf.py）")

    if args.issue_only:
        print(n)
        return

    entries = parse_history(args.history)
    if n not in entries:
        die(f"HISTORY.md（{args.history}）中没有「第 {n} 期」条目，"
            "请先运行 scripts/append_history.py 追加发刊史后再打 tag")
    e = entries[n]
    if not e["kanhao"] or not e["headline"]:
        die(f"HISTORY.md 第 {n} 期条目缺少刊号或头条字段，请检查/重跑 append_history.py")

    date = e["date"] or "未知"
    print(f"# CSSEC 周报 第 {n} 期")
    print(f"- 刊号：{e['kanhao']}")
    print(f"- 发刊：{date}")
    print(f"- 头条：{e['headline']}")
    print("附：本 Release 含 md / html / pdf 三份成品与 sources/ 中间稿。")


if __name__ == "__main__":
    main()
