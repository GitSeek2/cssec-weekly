"""事实核查辅助 —— 从定稿提取硬事实，与素材比对（SKILL.md 阶段六）。

提取的「硬事实」类型（可机械比对的）：
    - CVE 编号        `CVE-2026-1234`
    - 日期            `2026-08-14` / `8 月 14 日`
    - 数字            百分比、金额、带万/亿的量、≥4 位整数、小数（CVSS/权重等）

比对语料：成品同目录 sources/ 下的 *.md（信息池、头条素材、去重合并、
头条候选）与 raw/*.json（fetch_all 落盘的原始数据）。事实核对.md 与
审稿记录.md 是下游产物，排除以免循环自证。

输出：matched / unmatched 报告。unmatched 不是「一定错」——素材转写时
可能换了单位或语序——交人工/LLM 逐条裁决（回一手出处核实、改写或删除），
结论记入 sources/事实核对.md。本工具始终退出 0（裁决在流程层，门禁在
lint.py）；文件读不到才退非 0。

用法:
    uv run python scripts/check_facts.py "issues/CS26-0804-TP/CSSEC 周报 · 第 3 期.md"
    uv run python scripts/check_facts.py 成品.md --json
"""

import argparse
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md2html  # noqa: E402 —— 复用零件正则，跳过零件行

_CVE = re.compile(r"CVE-\d{4}-\d{4,7}", re.I)
_DATE_ISO = re.compile(r"\d{4}-\d{1,2}-\d{1,2}")
_DATE_CN = re.compile(r"\d{1,2}\s*月\s*\d{1,2}\s*日")
_NUM = re.compile(
    r"\d[\d,]*(?:\.\d+)?\s*(?:%"
    r"|万美元|万欧元|万英镑|万列伊|亿美元|亿欧元|美元|欧元|英镑|比特币|列伊|元"
    r"|万|亿"
    r"|家|人|款|次|条|个|名|位|台|笔|天|小时|分钟|秒|周|年)"
    r"|\d[\d,]*\.\d+"
    r"|\d{4,}")
_STRUCTURAL_PREFIX = ("#", ">", "- ", "出处", "刊号", "发刊", "下期预告",
                      "反馈与勘误", "**AI 撰写说明")
_STRUCTURAL_RE = re.compile(r"^\d+\.\s")   # 文献编号列表是引文不是主张
_NUM_BLACKLIST = re.compile(r"^(?:19|20)\d{2}$")  # 裸年份噪声太多，跳过


def _iter_claim_lines(lines):
    """产出 (行号, 已去 URL 的行文本)。跳过零件行/标题/引用块/出处/赛事数据行。"""
    in_fence = False
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not s:
            continue
        if any(s.startswith(p) for p in _STRUCTURAL_PREFIX) or _STRUCTURAL_RE.match(s):
            continue
        if md2html._DATELINE.match(s) or md2html._PUB_NO.match(s):
            continue
        if re.match(r"^-?\s*(竞赛时间|链接)[：:]", s):
            continue
        text = re.sub(r"https?://\S+", "", line)   # URL 里的数字不算事实
        yield i, text


def extract_facts(lines):
    """提取 (行号, 类型, 事实串) 列表。CVE/日期先提取并遮蔽，再提数字。"""
    facts = []
    for i, text in _iter_claim_lines(lines):
        spans = []
        for m in _CVE.finditer(text):
            facts.append((i, "CVE", m.group(0).upper()))
            spans.append(m.span())
        for m in _DATE_ISO.finditer(text):
            facts.append((i, "日期", m.group(0)))
            spans.append(m.span())
        for m in _DATE_CN.finditer(text):
            facts.append((i, "日期", re.sub(r"\s", "", m.group(0))))
            spans.append(m.span())
        masked = list(text)
        for a, b in spans:
            for k in range(a, b):
                masked[k] = "　"
        masked_text = "".join(masked)
        for m in _NUM.finditer(masked_text):
            # 数字是标识符一部分（GPT-5.6 / SHA-256）时不算独立事实
            a, b = m.start(), m.end()
            if a > 0 and re.match(r"[A-Za-z0-9_.\-]", masked_text[a - 1]):
                continue
            after = masked_text[b:b + 1]
            if after and re.match(r"[A-Za-z]", after):
                continue
            token = re.sub(r"\s", "", m.group(0))
            if _NUM_BLACKLIST.match(token):
                continue
            facts.append((i, "数字", token))
    seen, out = set(), []
    for i, kind, fact in facts:
        key = (kind, fact)
        if key not in seen:
            seen.add(key)
            out.append((i, kind, fact))
    return out


def load_corpus(md_path):
    """语料 = sources/*.md（排除下游产物）+ sources/raw/*.json。"""
    src_dir = os.path.join(os.path.dirname(os.path.abspath(md_path)), "sources")
    files = [f for f in sorted(glob.glob(os.path.join(src_dir, "*.md")))
             if os.path.basename(f) not in ("事实核对.md", "审稿记录.md")]
    files += sorted(glob.glob(os.path.join(src_dir, "raw", "*.json")))
    texts = []
    for f in files:
        try:
            texts.append(open(f, "r", encoding="utf-8", errors="replace").read())
        except OSError:
            pass
    return "\n".join(texts)


def _variants(fact):
    """一个事实的等价写法候选（去千分位逗号 / 去空格 / 全半角）。"""
    out = {fact, fact.replace(",", ""), re.sub(r"\s", "", fact)}
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})$", fact)
    if m:  # ISO 日期 ↔ 中文日期互查
        y, mo, d = m.groups()
        out.add("{}年{}月{}日".format(y, int(mo), int(d)))
        out.add("{}月{}日".format(int(mo), int(d)))
    m = re.match(r"(\d{1,2})月(\d{1,2})日$", fact)
    if m:
        mo, d = (int(x) for x in m.groups())
        for y in range(dt_years_floor(), dt_years_ceil()):
            out.add("{}-{:0>2}-{:0>2}".format(y, mo, d))
    return out


def _year_bounds():
    """中文日期转 ISO 时试近两年（今年/去年），避免环境时间不可用。"""
    import datetime
    y = datetime.date.today().year
    return y - 1, y + 1


def dt_years_floor():
    return _year_bounds()[0]


def dt_years_ceil():
    return _year_bounds()[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description="事实核查辅助（SKILL.md 阶段六）")
    ap.add_argument("input", help="定稿 Markdown 路径")
    ap.add_argument("--json", action="store_true", help="机器可读 JSON 输出")
    ap.add_argument("--corpus", default=None, help="语料目录（默认 <md>/sources）")
    args = ap.parse_args(argv)

    try:
        with open(args.input, "r", encoding="utf-8") as f:
            lines = f.read().split("\n")
    except OSError as e:
        print("错误: {}".format(e), file=sys.stderr)
        return 2

    facts = extract_facts(lines)
    if args.corpus:
        corpus = "\n".join(open(f, "r", encoding="utf-8", errors="replace").read()
                           for f in glob.glob(os.path.join(args.corpus, "*.md"))
                           + glob.glob(os.path.join(args.corpus, "raw", "*.json")))
    else:
        corpus = load_corpus(args.input)
    corpus_norm = re.sub(r"\s", "", corpus).replace(",", "")
    corpus_norm = corpus_norm.replace("，", "").replace("、", "")

    matched, unmatched = [], []
    for i, kind, fact in facts:
        hit = any(v.replace(",", "") in corpus_norm for v in _variants(fact))
        (matched if hit else unmatched).append((i, kind, fact))

    if args.json:
        print(json.dumps({
            "total": len(facts),
            "matched": len(matched),
            "unmatched": [{"line": i, "kind": k, "fact": f} for i, k, f in unmatched],
        }, ensure_ascii=False, indent=2))
        return 0

    print("check_facts: {}".format(os.path.basename(args.input)))
    print("=" * 56)
    print("硬事实 {} 条：matched {} / unmatched {}".format(
        len(facts), len(matched), len(unmatched)))
    if unmatched:
        print("-- unmatched（逐条裁决：核实 / 改写 / 删除，结论记入 sources/事实核对.md）--")
        for i, kind, fact in unmatched:
            print("  L{} [{}] {}".format(i, kind, fact))
    else:
        print("unmatched 为空。")
    print("=" * 56)
    print("提示：unmatched 不等于错误——素材转写可能换单位/语序；拿不准就回一手出处核实。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
