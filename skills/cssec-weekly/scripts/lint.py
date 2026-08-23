"""周报风格与结构门禁（分级 lint）。

检查项分两级：
    error   —— 红线（禁令 / 引语溯源 / 零件齐全性 / 溯源比对）。
               存在 error 即退出码 1 = 未定稿（SKILL.md 阶段七门禁）。
    warning —— 节奏配额（句长 / 标点数量 / 段落句数 / 被动密度）。
               只报告不阻断，按朗读感受酌情处理。

规则唯一事实源：本脚本。配额数字写在下方 RULES 区，文档只引用不重复
（写作风格.md Part 5 / 版面与零件.md 均指向本脚本）。零件识别正则从
md2html.py import 复用——转换器与门禁对「什么是零件」的判定永远一致。

溯源类检查（引语溯源 / 链接追溯 / AI 说明源列表）需要成品同目录的
sources/ 中间稿（信息池.md、头条素材.md 等）作语料；sources/ 缺失时
这些检查降级为 warning 提示，不阻断。

用法:
    uv run python scripts/lint.py <成品.md>            # 全检，人读报告
    uv run python scripts/lint.py <成品.md> --json     # 机器可读输出
    uv run python scripts/lint.py --list               # 列出全部规则与配额

输出:
    - 人读模式：按 error / warning 分组，每条 [规则] 行号: 摘录 → 提示；
      末尾汇总。error=0 且退出码 0 才算过门禁。
    - --json：{"ok": bool, "errors": [...], "warnings": [...]}
"""

import argparse
import glob
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import md2html  # noqa: E402 —— 复用零件识别正则，两处判定永远一致

# --------------------------------------------------------------------------- #
# 规则定义区（配额唯一事实源）
# --------------------------------------------------------------------------- #
QUOTAS = {
    "bold": 5,          # 加粗 ** 全篇上限
    "corner_quote": 2,  # 直角引号「」全篇上限
    "dash": 3,          # 破折号 —— 全篇上限
    "sentence": 40,     # 单句字数基准（超长提示）
    "brief_para": 3,    # 简讯单段句数上限
    "headline_para": 6, # 头条单段句数提示阈值（通常 3~5，叙事段可到 6）
    "passive_density": 8,  # 每 1000 字「遭/被」次数提示阈值
}

# 红线禁令：(规则名, 正则, 提示)。命中即 error。
BANNED = [
    ("空升华",
     r"这意味着|这说明了|这正是|再次说明|再次印证|再次证明|敲响警钟|任重道远"
     r"|是[^，。；\n]{1,8}的缩影|一张[^，。；\n]{1,6}背后|标志着[^，。\n]{0,14}进入",
     "把判断换成一个事实（写作风格 Part 4 A 类）"),
    ("替读者思考",
     r"值得注意的是|值得警惕的是|需要警惕的是|把视角拉远|纵观|换句话说"
     r"|总而言之|综上所述|既是[^，。\n]{1,10}也是|一方面[^。\n]{0,30}另一方面",
     "删元叙述标记，事实并放置（Part 4 B 类）"),
    ("喊话读者",
     r"对学生来说|作为安全从业者|作为学生|我们应该|我们需要|你要|你需要关注|你需要知道",
     "读者定位靠选题体现，不写在文字上（Part 4 B 类）"),
    ("惊人句式",
     r"这不是演习|真正的考验刚刚开始|一棍子捅穿|成了提款机",
     "回到机制描述（Part 4 C 类）"),
    ("不是X而是Y",
     r"(?:不再?是|并不是)[^，。；\n]{1,12}[，]?\s*而是",
     "对比句式只是换种说法复述，直接写事实（Part 4 C 类）"),
]

# 空建议：句内含建议动词但无具体版本/对象（Part 4 D 类）
EMPTY_ADVICE = re.compile(
    r"(?:应|建议|务必|请|需)[^。，\n]{0,6}(?:尽快|及时|立即|第一时间)?"
    r"(?:升级|更新|修复|打补丁|采取措施|加强防范|关注官方)"
    r"|(?:相关|受影响)(?:的)?(?:设备|系统|用户|版本)[^。\n]{0,4}应")
VERSION_HINT = re.compile(r"\d+(?:\.\d+)+")  # 句内有版本号 → 允许具体建议

EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF\U0000FE0F\U00002190-\U000021FF]")

ATTRIBUTION = re.compile(r"^[—\-–]{1,3}\s*")      # 引用块归属行
_CURLY = re.compile("“([^”\\n]{4,})”")
_PUBNO_LINE = re.compile(r"^刊号[：:]\s*(CS\d{2}-\d{4}-TP)\s*$")
_LINK = re.compile(r"\[([^\]\n]*)\]\(([^)\n]+)\)|(?<![(\[])(https?://[^\s<>)\]，。；！？]+)")

SECTION_ORDER = ["态势感知", "漏洞情报", "前沿技术", "政策法规", "赛事活动", "未定"]


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def _strip_code_fences(text):
    """去掉代码围栏内容（版面禁令不管代码块）。"""
    return re.sub(r"```.*?```", "", text, flags=re.S)


def _strip_inline_markup(s):
    return md2html.strip_inline(s)


def _sentence_len(s):
    """单句字数：去掉行内代码 / 链接 URL / 空白后计。"""
    s = re.sub(r"`[^`\n]+`", "", s)
    s = re.sub(r"\[[^\]\n]*\]\([^)\n]*\)", "", s)
    s = re.sub(r"https?://\S+", "", s)
    return len(re.sub(r"\s", "", s))


def _split_sentences(para):
    """段落 → 句列表（按 。！？切，保留原文）。"""
    parts = re.split(r"(?<=[。！？])", para)
    return [p for p in (x.strip() for x in parts) if p]


def _norm(s):
    """溯源比对用的归一化：去空白与常见标点变体。"""
    s = unicodedata.normalize("NFKC", s)
    return re.sub(r"[\s，。、；：！？“”‘’「」『』—…·,.;:!?\"'()（）\[\]]", "", s)


def _excerpt(s, n=36):
    s = re.sub(r"\s+", " ", s).strip()
    return s if len(s) <= n else s[: n - 1] + "…"


def _iter_body_lines(lines):
    """产出 (行号, 行文本)，跳过代码围栏与空行。"""
    in_fence = False
    for i, line in enumerate(lines, 1):
        if line.strip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence or not line.strip():
            continue
        yield i, line


def _is_structural(line):
    """零件行 / 出处行 / 标题 / 列表行（含文献编号列表）/ 引用块 —— 不参与句级配额。"""
    s = line.strip()
    return (s.startswith("#") or s.startswith(">") or s.startswith("- ")
            or re.match(r"^\d+\.\s", s) is not None or s.startswith("出处")
            or s.startswith("**AI 撰写说明")
            or md2html._PUB_NO.match(s) or md2html._DATELINE.match(s)
            or md2html._PREVIEW.match(s) or md2html._FEEDBACK.match(s))


# --------------------------------------------------------------------------- #
# 文档结构解析（行级，受控格式足够）
# --------------------------------------------------------------------------- #
def parse_doc(lines):
    doc = {"h1": "", "sections": []}   # sections: [{name, headline?, blocks}]
    cur = None
    for line in lines:
        if line.startswith("# ") and not doc["h1"]:
            doc["h1"] = line[2:].strip()
            continue
        if line.startswith("## "):
            name = line[3:].strip()
            cur = {"name": name, "headline": name.startswith("本期主题"),
                   "lines": []}
            doc["sections"].append(cur)
            continue
        if cur is not None:
            cur["lines"].append(line)
    return doc


def split_h3_blocks(section_lines):
    """板块内按 H3 切条目；返回 [(h3标题, [段落])]，段落为多行合成的字符串。"""
    blocks, cur_title, buf = [], None, []
    for line in section_lines:
        if line.startswith("### "):
            if buf:
                blocks.append((cur_title, "\n".join(buf).strip()))
            cur_title, buf = line[4:].strip(), []
        else:
            buf.append(line)
    if buf:
        blocks.append((cur_title, "\n".join(buf).strip()))
    return blocks


def paragraphs_of(block_text):
    """条目文本 → 正文段落列表（跳过标题行/出处行/引用块/列表/文献）。"""
    out = []
    for para in block_text.split("\n\n"):
        p = para.strip()
        if not p:
            continue
        lines = [l for l in p.split("\n") if l.strip()]
        if any(_is_structural(l) for l in lines):
            continue
        if _strip_inline_markup(p) == "相关文献":
            continue
        out.append("".join(_strip_inline_markup(l) for l in lines))
    return out


# --------------------------------------------------------------------------- #
# 检查器
# --------------------------------------------------------------------------- #
def check_text_rules(text_lines, errs, warns):
    text = _strip_code_fences("\n".join(text_lines))

    m = EMOJI.search(text)
    if m:
        errs.append(("emoji", 0, m.group(0), "版面全面禁用 emoji"))
    for i, line in _iter_body_lines(text_lines):
        s = line.strip()
        if s.startswith(">"):  # 引用块内是他人原话，禁令只管正文
            continue
        if "→" in _strip_inline_markup(s):
            errs.append(("箭头", i, _excerpt(s), "流程描述用顿号或连词（Part 4）"))
        plain = _strip_inline_markup(s)
        for name, pat, hint in BANNED:
            for m in re.finditer(pat, plain):
                errs.append((name, i, _excerpt(m.group(0)), hint))
        m = EMPTY_ADVICE.search(plain)
        if m and not VERSION_HINT.search(plain):
            errs.append(("空建议结尾", i, _excerpt(m.group(0)),
                         "建议要具体到版本/动作/对象，写不出就删（Part 4 D 类）"))

    # ---- warning：标记配额（全篇计数）----
    bold = len(re.findall(r"\*\*[^*\n]+\*\*", text))
    if bold > QUOTAS["bold"]:
        warns.append(("加粗配额", 0,
                      "加粗 {} 处 > 上限 {}".format(bold, QUOTAS["bold"]),
                      "仅关键数字/CVE/产品名"))
    corner = text.count("「")
    if corner > QUOTAS["corner_quote"]:
        warns.append(("直角引号配额", 0,
                      "「」{} 处 > 上限 {}".format(corner, QUOTAS["corner_quote"]),
                      "仅冷僻术语首现"))
    dash_lines = [l for l in text.split("\n")
                  if not l.strip().startswith(">")]   # 引用块（含归属行）不计
    dash = sum(l.count("——") for l in dash_lines)
    if dash > QUOTAS["dash"]:
        warns.append(("破折号配额", 0,
                      "—— {} 处 > 上限 {}".format(dash, QUOTAS["dash"]),
                      "仅补充说明或转折"))
    body_chars = len(re.sub(r"\s", "", _strip_inline_markup(text)))
    passive = len(re.findall(r"[遭被]", text))
    if body_chars > 200 and passive / max(body_chars, 1) * 1000 > QUOTAS["passive_density"]:
        warns.append(("被动句密度", 0,
                      "「遭/被」{} 处 / 千字".format(round(
                          passive / max(body_chars, 1) * 1000, 1)),
                      "主动句更像新闻（动作 3）"))
    return text


def check_sentences(section, errs, warns):
    """句级与段级配额（warning）：句长、段落句数、连续三句同构。"""
    is_headline = section["headline"]
    for title, block in split_h3_blocks(section["lines"]):
        for para in paragraphs_of(block):
            sents = _split_sentences(para)
            limit = QUOTAS["headline_para"] if is_headline else QUOTAS["brief_para"]
            if len(sents) > limit:
                warns.append(("段落句数超限", 0,
                              "「{}」单段 {} 句 > {}".format(
                                  _excerpt(title or para, 16), len(sents), limit),
                              "拆段或删句"))
            for s in sents:
                n = _sentence_len(s)
                if n > QUOTAS["sentence"]:
                    warns.append(("单句超长", 0,
                                  "{}（{} 字）".format(_excerpt(s), n),
                                  "朗读换气两次以上则拆"))
            for k in range(len(sents) - 2):
                a, b, c = sents[k:k + 3]
                if a[:2] == b[:2] == c[:2] and len(a[:2]) == 2 \
                        and not a[:1].isdigit():
                    warns.append(("连续三句同构", 0,
                                  "「{}…」×3 以「{}」开头".format(
                                      _excerpt(a, 12), a[:2]),
                                  "中间句改结构（疑似排比）"))
                    break


def check_masthead(doc, errs):
    h1 = doc["h1"]
    if not h1:
        errs.append(("零件缺失", 1, "无 H1 刊头",
                     "需 `# CSSEC 周报 第 N 期（YYYY-MM-DD ~ YYYY-MM-DD）`"))
        return
    if not md2html._MASTHEAD_ISSUE.search(h1):
        errs.append(("零件缺失", 1, _excerpt(h1), "H1 缺期号「第 N 期」"))
    if not md2html._MASTHEAD_RANGE.search(h1):
        errs.append(("零件缺失", 1, _excerpt(h1), "H1 缺日期区间"))


def check_parts(lines, doc, errs):
    have = {"pubno": False, "dateline": False, "lede": False,
            "feedback": False, "colophon": False, "literature": False}
    first_h2 = next((i for i, l in enumerate(lines, 1) if l.startswith("## ")),
                    len(lines))
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if _PUBNO_LINE.match(s):
            have["pubno"] = True
        elif md2html._DATELINE.match(s):
            have["dateline"] = True
        elif md2html._FEEDBACK.match(s):
            have["feedback"] = True
        elif md2html._COLOPHON.match(s):
            have["colophon"] = True
        elif _strip_inline_markup(s) == "相关文献":
            have["literature"] = True
        elif 1 < i < first_h2 and s and not s.startswith(("#", ">", "刊号", "发刊")):
            have["lede"] = True
    if not have["pubno"]:
        errs.append(("零件缺失", 0, "刊号行", "需 `刊号：CSYY-MMWW-TP`（H1 下、导读前）"))
    if not have["dateline"]:
        errs.append(("零件缺失", 0, "发刊电头", "需 `发刊：YYYY-MM-DD`（导读后）"))
    if not have["lede"]:
        errs.append(("零件缺失", 0, "本期导读", "H1 与首个 H2 之间需 2~3 句导读"))
    if not have["feedback"]:
        errs.append(("零件缺失", 0, "反馈入口", "需 `反馈与勘误：[提交 issue](url)`"))
    if not have["colophon"]:
        errs.append(("零件缺失", 0, "AI 撰写说明", "文末需以 `---` 引出 AI 撰写说明"))
    headline = next((s for s in doc["sections"] if s["headline"]), None)
    if headline and not have["literature"]:
        errs.append(("零件缺失", 0, "头条相关文献",
                     "「本期主题」末尾需附「相关文献」小节"))


def collect_quotes(lines):
    """收集需溯源的引语：行内“…”（≥4 字）与引用块正文（非归属行）。"""
    quotes = []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if s.startswith(">"):
            body = re.sub(r"^>\s?", "", s).strip()
            if body and not ATTRIBUTION.match(body) \
                    and _strip_inline_markup(body) != "相关文献":
                for q in re.findall(r"“([^”\n]+)”", body) or [body]:
                    quotes.append((i, q))
        else:
            for q in _CURLY.findall(line):
                quotes.append((i, q))
    return [(i, q) for i, q in quotes if len(_norm(q)) >= 4]


def collect_links(text):
    urls = []
    for m in _LINK.finditer(text):
        url = m.group(2) or m.group(0)
        if url.startswith(("http://", "https://")):
            urls.append(url.rstrip(".,;:!?。，；：！？"))
    return urls


def parse_colophon_sources(lines):
    """从 AI 撰写说明「基于 A、B、C 等公开权威信息源」通用提取列出的源名。"""
    body = []
    grab = False
    for line in lines:
        if md2html._COLOPHON.match(line.strip()):
            grab = True
            body.append(line)
            continue
        if grab:
            if line.strip().startswith("---") or line.startswith("#"):
                break
            body.append(line)
    text = "".join(body)
    m = re.search(r"基于(.+?)(?:等公开权威信息源)?(?:整理|撰写)", text)
    if not m:
        m = re.search(r"基于(.+?)等", text)
    if not m:
        return []
    return [t.strip() for t in re.split(r"[、，,]", m.group(1)) if t.strip()]


def check_traceability(md_path, lines, errs, warns):
    """引语溯源 / 链接追溯 / AI 说明源列表 —— 语料 = sources/*.md + sources/raw/*.json。"""
    src_dir = os.path.join(os.path.dirname(os.path.abspath(md_path)), "sources")
    # 审稿记录 / 事实核对是下游产物（会引用草稿句子），排除以防循环自证
    # ——与 check_facts.py 的语料策略一致。
    downstream = ("审稿记录.md", "事实核对.md")
    src_files = [f for f in sorted(glob.glob(os.path.join(src_dir, "*.md")))
                 if os.path.basename(f) not in downstream]
    src_files += sorted(glob.glob(os.path.join(src_dir, "raw", "*.json")))
    if not src_files:
        warns.append(("溯源语料缺失", 0, "未找到 sources/ 素材",
                      "引语溯源/链接追溯/AI 源列表检查跳过（降级）"))
        return
    corpus = "\n".join(open(f, "r", encoding="utf-8",
                            errors="replace").read() for f in src_files)
    corpus_norm = _norm(corpus)
    corpus_raw = corpus.replace(" ", "")

    # 1) 引语溯源
    for i, q in collect_quotes(lines):
        nq = _norm(q)
        if nq and nq not in corpus_norm and q.replace(" ", "") not in corpus_raw:
            errs.append(("引语溯源", i, "“{}”".format(_excerpt(q, 30)),
                         "未在 sources/ 素材中找到——核实原文，或把原话补录进头条素材.md"))

    # 2) 链接追溯（反馈入口行的仓库链接是零件，白名单）
    md_text = "\n".join(lines)
    corpus_links = set(collect_links(corpus))
    skip = set()
    for line in lines:
        if md2html._FEEDBACK.match(line.strip()):
            skip.update(collect_links(line))
    for url in set(collect_links(md_text)) - skip:
        if url not in corpus_links and url not in corpus:
            errs.append(("链接追溯", 0, url,
                         "成品链接未出现在 sources/ 素材中——补录出处或核对 URL"))

    # 3) AI 说明源列表 ⊆ 实际使用
    listed = parse_colophon_sources(lines)
    if listed:
        used_corpus = corpus + "\n" + md_text
        for name in listed:
            if name not in used_corpus:
                errs.append(("AI 说明源列表", 0, name,
                             "列出的源未在本期素材/成品中出现——从未使用的源删去"))


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def lint(md_path):
    with open(md_path, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")
    errs, warns = [], []
    check_text_rules(lines, errs, warns)
    doc = parse_doc(lines)
    for section in doc["sections"]:
        if section["name"].startswith("下期预告"):
            continue
        check_sentences(section, errs, warns)
    check_masthead(doc, errs)
    check_parts(lines, doc, errs)
    check_traceability(md_path, lines, errs, warns)
    # 排序：error 优先，按规则名
    errs.sort(key=lambda e: (e[0], e[1]))
    warns.sort(key=lambda w: w[0])
    return doc, errs, warns


def report_human(md_path, doc, errs, warns):
    print("lint: {}".format(os.path.basename(md_path)))
    print("=" * 60)
    if errs:
        print("== error（红线，阻断定稿）共 {} 条 ==".format(len(errs)))
        for rule, line, excerpt, hint in errs:
            print("  [{rule}] {loc}: {excerpt}".format(
                rule=rule, loc="L{}".format(line) if line else "全文",
                excerpt=excerpt))
            print("      → {}".format(hint))
    else:
        print("== error（红线）0 条 ==")
    if warns:
        print("-- warning（节奏配额，酌情处理）共 {} 条 --".format(len(warns)))
        for rule, line, excerpt, hint in warns:
            print("  [{rule}] {excerpt}".format(rule=rule, excerpt=excerpt))
            print("      · {}".format(hint))
    print("=" * 60)
    ok = not errs
    print("结论：error {} / warning {} —— {}".format(
        len(errs), len(warns),
        "通过（可定稿）" if ok else "未通过（error 须清零）"))
    return ok


RULE_TABLE = """规则清单（lint.py --list）
======================== error 红线（阻断）========================
空升华        这意味着/这说明了/再次说明/是…的缩影/敲响警钟/任重道远…
替读者思考    值得注意的是/把视角拉远/纵观/换句话说/综上所述/既是…也是…
喊话读者      对学生来说/作为安全从业者/我们应该/你需要关注…
惊人句式      这不是演习/真正的考验刚刚开始/一棍子捅穿/成了提款机
不是X而是Y    （不再?是|并不是）…而是…
空建议结尾    应尽快升级/建议及时更新/相关设备应…（句内有版本号则放行）
emoji         任何 emoji
箭头 →        正文（代码块除外）
引语溯源      “…”与引用块正文必须能在 sources/*.md 中找到
链接追溯      成品所有链接必须出现在 sources/ 素材中
AI 说明源列表 列出的信息源必须在本期素材/成品中出现
零件齐全性    H1 期号+区间 / 刊号行 / 导读 / 发刊电头 / 反馈入口 /
              AI 撰写说明 / 头条「相关文献」（正则与 md2html.py 共用）
======================== warning 配额（报告）========================
加粗 ≤{bold} 处            直角引号「」≤{corner_quote} 处
破折号—— ≤{dash} 处          单句 >{sentence} 字提示
简讯单段 >{brief_para} 句提示    头条单段 >{headline_para} 句提示
「遭/被」密度 >{passive_density}/千字提示  连续三句同构（疑似排比）
===================================================================="""


def main(argv=None):
    ap = argparse.ArgumentParser(description="周报风格与结构门禁（分级 lint）")
    ap.add_argument("input", nargs="?", help="待检 Markdown 路径")
    ap.add_argument("--list", action="store_true", help="列出全部规则与配额")
    ap.add_argument("--json", action="store_true", help="机器可读 JSON 输出")
    args = ap.parse_args(argv)

    if args.list or not args.input:
        if args.list:
            print(RULE_TABLE.format(**QUOTAS))
            return 0
        ap.error("需要输入文件（或 --list）")

    try:
        doc, errs, warns = lint(args.input)
    except Exception as e:  # noqa: BLE001
        print("错误: {}".format(e), file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({
            "ok": not errs,
            "errors": [{"rule": r, "line": l, "excerpt": e, "hint": h}
                       for r, l, e, h in errs],
            "warnings": [{"rule": r, "line": l, "excerpt": e, "hint": h}
                         for r, l, e, h in warns],
        }, ensure_ascii=False, indent=2))
        return 0 if not errs else 1
    ok = report_human(args.input, doc, errs, warns)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
