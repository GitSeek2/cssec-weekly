"""把新一期的发刊元数据追加进 HISTORY.md（发刊史）。

从 issues/<刊号>/ 的成品 md 里提取「刊号 / 发刊日期 / 头条标题」（头条取
`## 本期主题：` 冒号后文本），按「## 第 N 期（YYYY-MM-DD 发刊）」小节追加到
HISTORY.md。幂等：HISTORY 中已有该期小节则跳过，不重复追加。

用法:
    uv run python scripts/append_history.py                        # 自动定位最新一期
    uv run python scripts/append_history.py --dirname CS26-0802-TP

之后用刊号打 tag 并推送，GitHub Actions 会依据 HISTORY.md 自动发布 Release
（.github/workflows/release.yml）。
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
_FIELD = re.compile(r"^(刊号|发刊)\s*[:：]\s*(.+)$", re.UNICODE)
_HEADLINE = re.compile(r"^##\s*本期主题\s*[:：]\s*(.+)$", re.UNICODE)
_SECTION = re.compile(r"^##\s*第\s*([0-9]+)\s*期", re.UNICODE)


def die(msg):
    print(f"错误：{msg}", file=sys.stderr)
    sys.exit(1)


def latest_dirname(issues_dir):
    """返回最大期号目录名（最新一期）；issues 为空则返回 None。"""
    best = None
    for name in os.listdir(issues_dir):
        sub = os.path.join(issues_dir, name)
        if not os.path.isdir(sub):
            continue
        for f in os.listdir(sub):
            m = _ISSUE.search(f)
            if m:
                n = int(m.group(1))
                if best is None or n > best[0]:
                    best = (n, name)
                break
    return best[1] if best else None


def extract_md(dirpath):
    """从期目录成品 md 提取 (issue, kanhao, date, headline)。缺字段则报错。"""
    md = None
    for f in os.listdir(dirpath):
        if f.endswith(".md") and _ISSUE.search(f):
            md = os.path.join(dirpath, f)
            break
    if not md:
        die(f"目录 {dirpath} 中未找到含「第 N 期」的成品 md")
    issue = int(_ISSUE.search(os.path.basename(md)).group(1))

    kanhao = date = headline = ""
    with open(md, encoding="utf-8") as f:
        for raw in f:
            ln = raw.strip()
            fm = _FIELD.match(ln)
            if fm:
                key, val = fm.group(1), fm.group(2).strip()
                if key == "刊号" and not kanhao:
                    kanhao = val
                elif key == "发刊" and not date:
                    date = val
                continue
            hm = _HEADLINE.match(ln)
            if hm:
                headline = hm.group(1).strip()

    missing = [k for k, v in (("刊号", kanhao), ("发刊日期", date),
                              ("头条（## 本期主题：）", headline)) if not v]
    if missing:
        die(f"{os.path.basename(md)} 缺少字段：{', '.join(missing)}")
    return issue, kanhao, date, headline


def existing_issues(path):
    """HISTORY.md 中已有的期号集合。"""
    out = set()
    if not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for ln in f:
            m = _SECTION.match(ln)
            if m:
                out.add(int(m.group(1)))
    return out


def main():
    ap = argparse.ArgumentParser(description="追加一期发刊史到 HISTORY.md")
    ap.add_argument("--dirname", default=None,
                    help="期目录刊号（如 CS26-0802-TP；缺省自动定位最新一期）")
    ap.add_argument("--issues-dir", default=ISSUES_DIR, help="成品存档目录（默认仓库根 issues/）")
    ap.add_argument("--history", default=HISTORY, help="HISTORY.md 路径（默认仓库根）")
    args = ap.parse_args()

    dirname = args.dirname or latest_dirname(args.issues_dir)
    if not dirname:
        die(f"{args.issues_dir} 下没有成品期目录")
    dirpath = os.path.join(args.issues_dir, dirname)
    if not os.path.isdir(dirpath):
        die(f"目录不存在：{dirpath}")

    issue, kanhao, date, headline = extract_md(dirpath)
    if issue in existing_issues(args.history):
        print(f"跳过：HISTORY.md 已含「第 {issue} 期」条目（幂等，无变更）")
        return

    block = (
        f"\n## 第 {issue} 期（{date} 发刊）\n"
        f"- 刊号：{kanhao}\n"
        f"- 头条：{headline}\n"
    )
    with open(args.history, "a", encoding="utf-8") as f:
        f.write(block)
    print(f"已追加 HISTORY.md 第 {issue} 期条目：{kanhao}")


if __name__ == "__main__":
    main()
