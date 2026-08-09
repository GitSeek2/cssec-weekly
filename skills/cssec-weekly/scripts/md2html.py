"""周报 Markdown → 自包含报刊风格 HTML 转换器。

把一篇写好的 Markdown 周报（周报.md）转成单文件、内嵌 CSS、离线可看的
报刊风格 HTML 版（周报.html）。版式借鉴 opencode.ai 文档站的极简/严谨/美观
设计语言（暖白纸面、发丝线、直角、mono 数据、克制的暗色下划线链接、print 样式），
但整体仍是报刊版式，主题色 #016737。样式规格见 ../references/HTML设计.md。

做的事：
    1. 解析受控 Markdown 子集（H1-H4 / 段落 / 行内粗体斜体代码链接 /
       有序无序列表 / 引用 / GFM 表格 / 分隔线 / 代码围栏）。
    2. 识别周报的报刊零件（H1→刊头、刊号→报头刊号、导读→导读框、发刊→电头、
       H2→版眉、本期主题→头条版、H3→条目标题、出处→mono 出处行、
       竞赛时间/链接→mono 数据行、相关文献→文献块、下期预告→预告框、
       反馈→反馈行、AI 撰写说明→报尾）。
    3. 渲染为单个自包含 HTML 文件（CSS 全内嵌、无外部 CSS/JS；仅头部加载
       Google Fonts 网络字体——官方国内镜像 fonts.googleapis.cn，JetBrains Mono
       + Noto Serif SC，display:swap，断网/镜像失效自动回退系统字栈；自带 print 样式）。

用法:
    uv run python scripts/md2html.py ../../issues/CS26-0801-TP/CSSEC 周报 · 第 1 期.md
    uv run python scripts/md2html.py 报告.md -o 报告.html --title "CSSEC 周报"

输出:
    - 默认：输入同目录、同名 .html（周报.md → 周报.html），成功打印一行
      「已生成: <绝对路径>」。
    - 失败：stderr 打印错误，exit 1。

零第三方 Python 依赖（仅标准库）、确定性（无时间戳/随机，输出逐字节可复现）；
HTML 头部加载 Google Fonts 网络字体（官方国内镜像 fonts.googleapis.cn，见常量
FONT_CSS_URL，可用 --font-css / 环境变量 CSSEC_FONT_CSS 覆盖，传空串禁用）。
"""

import argparse
import html
import os
import re
import sys
from urllib.parse import urlparse

# --------------------------------------------------------------------------- #
# 行内 tokenizer：单条 alternation，构造互不干扰
# --------------------------------------------------------------------------- #
_INLINE = re.compile(
    r"(!\[[^\]\n]*\]\([^)\n]*\)"        # 图片 ![alt](url)（先于链接）
    r"|`[^`\n]+`"                       # 行内代码
    r"|\*\*[^*\n]+\*\*"                 # 粗体（先于斜体）
    r"|\*[^*\n]+\*"                     # 斜体
    r"|\[[^\]\n]*\]\([^)\n]*\)"         # 行内链接 [text](url)
    r"|https?://[^\s<>]+)"              # 裸 URL（保守 autolink）
)

_LINK_SCHEMES = ("http:", "https:", "mailto:")
_STRIP_URL_TAIL = ".,;:!?。，；：！？)]}>」」"   # 裸 URL 尾部收尾符号

# 网络字体 CSS（Google Fonts 官方国内镜像：fonts.googleapis.cn + fonts.gstatic.cn，
# 国内直连无需代理）。报刊衬线 Noto Serif SC + 技术 mono JetBrains Mono，display:swap
# 保证字体未就绪时先以系统回退栈渲染、就绪后再换。可用 --font-css 或环境变量
# CSSEC_FONT_CSS 覆盖（换其他镜像/自托管）；传空字符串禁用网络字体（纯系统字栈）。
FONT_CSS_URL = (
    "https://fonts.googleapis.cn/css2"
    "?family=JetBrains+Mono:wght@400;500;600;700"
    "&family=Noto+Serif+SC:wght@400;500;600;700"
    "&display=swap"
)


def _render_link(url, label):
    """链接渲染：scheme 白名单，危险的（javascript: 等）一律降级为纯文本。"""
    if not url.startswith(_LINK_SCHEMES):
        return html.escape(label)
    return '<a href="{}">{}</a>'.format(html.escape(url, quote=True),
                                        render_inline(label))


def render_inline(text):
    """把一段行内 Markdown 渲染为 HTML（转义 + 构造替换）。"""
    parts = _INLINE.split(text)
    out = []
    for idx, part in enumerate(parts):
        if idx % 2 == 0:
            out.append(html.escape(part))
            continue
        m_code = re.fullmatch(r"`([^`\n]+)`", part)
        if m_code:
            out.append("<code>{}</code>".format(html.escape(m_code.group(1))))
            continue
        m_bold = re.fullmatch(r"\*\*([^*\n]+)\*\*", part)
        if m_bold:
            out.append("<strong>{}</strong>".format(render_inline(m_bold.group(1))))
            continue
        m_em = re.fullmatch(r"\*([^*\n]+)\*", part)
        if m_em:
            out.append("<em>{}</em>".format(render_inline(m_em.group(1))))
            continue
        m_img = re.fullmatch(r"!\[([^\]\n]*)\]\(([^)\n]*)\)", part)
        if m_img:
            src = m_img.group(2).strip()
            if src.startswith(_LINK_SCHEMES):
                out.append('<img src="{}" alt="{}">'.format(
                    html.escape(src, quote=True), html.escape(m_img.group(1))))
            else:  # 危险图片地址：降级为纯文本 alt
                out.append(html.escape(m_img.group(1)))
            continue
        m_link = re.fullmatch(r"\[([^\]\n]*)\]\(([^)\n]*)\)", part)
        if m_link:
            out.append(_render_link(m_link.group(2).strip(), m_link.group(1)))
            continue
        # 裸 URL：去掉尾部收尾符号后 autolink
        url = re.sub(r"[{}]+$".format(re.escape(_STRIP_URL_TAIL)), "", part)
        out.append('<a href="{}">{}</a>'.format(html.escape(url, quote=True),
                                                html.escape(url)))
    return "".join(out)


def strip_inline(text):
    """剥离行内标记（用于识别纯粗体的 相关文献 / AI 撰写说明 等行）。"""
    s = re.sub(r"`([^`\n]+)`", r"\1", text)
    s = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", s)
    s = re.sub(r"\*([^*\n]+)\*", r"\1", s)
    s = re.sub(r"\[([^\]\n]*)\]\([^)\n]*\)", r"\1", s)
    return s.strip()


# --------------------------------------------------------------------------- #
# 块扫描：行级状态机
# --------------------------------------------------------------------------- #
_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_HR = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")
_LIST = re.compile(r"^(\s*)([-*+]|\d+\.)\s+(.*)$")
_TABLE_SEP = re.compile(r"^\s*\|?[\s:\-|]+\|?\s*$")


def read_document(path):
    """读入 Markdown 文件（utf-8）。解码失败抛异常，由 main 捕获退 1。"""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _flush_paragraph(out, buf, line_no):
    if buf:
        out.append({"type": "p", "text": "\n".join(buf), "line_no": line_no})
        buf.clear()


def _flush_list(out, state):
    if state is not None:
        out.append({"type": state["kind"], "items": state["items"],
                    "line_no": state["line_no"]})


def scan_blocks(text):
    """行级状态机：把文本切成扁平的块列表。"""
    lines = text.split("\n")
    out = []
    para_buf = []
    para_line = 1
    list_state = None
    i = 0
    n = len(lines)

    def flush_para():
        nonlocal para_buf, para_line
        _flush_paragraph(out, para_buf, para_line)

    def flush_list():
        nonlocal list_state
        _flush_list(out, list_state)
        list_state = None

    while i < n:
        raw = lines[i]
        line = raw.rstrip("\n")
        stripped = line.strip()
        cur = i + 1

        if stripped == "":
            flush_para()
            flush_list()
            i += 1
            continue

        # 代码围栏
        if stripped.startswith("```"):
            flush_para()
            flush_list()
            fenced = [line]
            i += 1
            while i < n and not lines[i].rstrip("\n").strip().startswith("```"):
                fenced.append(lines[i].rstrip("\n"))
                i += 1
            if i < n:  # 吃掉收尾围栏行
                i += 1
            out.append({"type": "pre", "lines": fenced[1:], "line_no": cur})
            continue

        # 标题
        m = _HEADING.match(line)
        if m:
            flush_para()
            flush_list()
            level = len(m.group(1))
            out.append({"type": "h%d" % level, "level": level,
                        "text": m.group(2).strip(), "line_no": cur})
            i += 1
            continue

        # 分隔线
        if _HR.match(line):
            flush_para()
            flush_list()
            out.append({"type": "hr", "line_no": cur})
            i += 1
            continue

        # 引用块：连续 > 行聚块
        if line.startswith(">"):
            flush_para()
            flush_list()
            quote = []
            while i < n and lines[i].startswith(">"):
                quote.append(re.sub(r"^>\s?", "", lines[i].rstrip("\n")))
                i += 1
            out.append({"type": "blockquote", "lines": quote, "line_no": cur})
            continue

        # 列表项
        m = _LIST.match(line)
        if m:
            flush_para()
            marker = m.group(2)
            kind = "ol" if marker[0].isdigit() else "ul"
            depth = 1 + (len(m.group(1)) // 2)
            if list_state is None or list_state["kind"] != kind:
                flush_list()
                list_state = {"kind": kind, "items": [], "line_no": cur}
            list_state["items"].append((depth, m.group(3)))
            i += 1
            continue

        # GFM 表格：当前行含 |，下一行是分隔行
        if "|" in line and i + 1 < n and "|" in lines[i + 1]:
            sep = lines[i + 1].strip()
            if _TABLE_SEP.match(sep) and re.search(r"\|[\s:]*[-]+[\s:]*\|", sep):
                flush_para()
                flush_list()
                rows = [[c.strip() for c in line.strip().strip("|").split("|")]]
                i += 2  # 跳过分隔行
                while i < n and lines[i].strip() != "" and "|" in lines[i]:
                    rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                    i += 1
                out.append({"type": "table", "rows": rows, "line_no": cur})
                continue

        # 普通段落行：连续非空、非特殊行并入同一段
        flush_list()
        if not para_buf:
            para_line = cur
        para_buf.append(line)
        i += 1

    flush_para()
    flush_list()
    return out


# --------------------------------------------------------------------------- #
# 结构 pass：报刊零件识别 + 分节
# --------------------------------------------------------------------------- #
_MASTHEAD_ISSUE = re.compile(r"第\s*([0-9０-９]+)\s*期")
_MASTHEAD_RANGE = re.compile(
    r"[（(]\s*(\d{4}-\d{1,2}-\d{1,2}\s*[~～]\s*\d{4}-\d{1,2}-\d{1,2})\s*[）)]")
_DATELINE = re.compile(r"^发刊[：:]\s*\d{4}-\d{1,2}-\d{1,2}")
_PUB_NO = re.compile(r"^刊号[：:]")
_SOURCE = re.compile(r"^出处[：:]")
_PREVIEW = re.compile(r"^下期预告[：:]")
_FEEDBACK = re.compile(r"^反馈与勘误[：:]")
_COLOPHON = re.compile(r"^\*\*AI 撰写说明\*\*[：:]")
_COLOPHON_AGENT = re.compile(r"本文由(.+?)调用(.+?)基于")
_DATA_LINE = re.compile(r"^(竞赛时间|链接)[：:]")
_QUOTE_ATTR = re.compile(r"^[—-]{1,3}\s*")
_LABEL_COLON = re.compile(r"^[^：:]*[：:]")


def parse_masthead(text):
    """从 H1 拆出 刊名 / 期号 / 日期区间（容忍全半角与空格）。"""
    m = _MASTHEAD_ISSUE.search(text)
    name = text.strip()
    issue = ""
    if m:
        issue = m.group(1)
        name = text[:m.start()].strip()
    mr = _MASTHEAD_RANGE.search(text)
    rng = mr.group(1).replace("～", "~") if mr else ""
    return {"name": name, "issue": issue, "range": rng}


def classify_paragraph(text):
    """段落角色：dateline / source / preview / feedback / colophon /
    literature-head / plain。"""
    if _DATELINE.match(text):
        return "dateline"
    if _PUB_NO.match(text):
        return "publication-no"
    if _SOURCE.match(text):
        return "source"
    if _PREVIEW.match(text):
        return "preview"
    if _FEEDBACK.match(text):
        return "feedback"
    if strip_inline(text) == "相关文献":
        return "literature-head"
    if _COLOPHON.match(text):
        return "colophon"
    return "plain"


def _block_role(b):
    t = b.get("type")
    if t in ("h1", "h2", "h3", "h4", "hr", "table", "pre", "blockquote"):
        return t
    if t == "p":
        return classify_paragraph(b["text"])
    if t == "ul":
        if b["items"] and all(_DATA_LINE.match(txt) for _, txt in b["items"]):
            return "event-meta"
        return "ul"
    return t  # ol → 'ol'


def _group_section(children):
    """把一节 children 分成 lead / stories / literature。"""
    lead, stories, literature = [], [], []
    current_story = None
    pending_lit_head = None
    for b in children:
        role = _block_role(b)
        if b["type"] == "h3":
            current_story = {"head": b, "children": []}
            stories.append(current_story)
        elif role == "literature-head":
            # 吞掉前导分隔线（文献块自带顶线）
            if current_story and current_story["children"] \
                    and current_story["children"][-1]["type"] == "hr":
                current_story["children"].pop()
            elif lead and lead[-1]["type"] == "hr":
                lead.pop()
            pending_lit_head = b
        elif b["type"] == "ol" and pending_lit_head is not None:
            literature.append({"head": pending_lit_head, "list": b})
            pending_lit_head = None
        else:
            if current_story is None:
                lead.append(b)
            else:
                current_story["children"].append(b)
    if pending_lit_head is not None:
        (lead if current_story is None else current_story["children"]).append(
            pending_lit_head)
    return {"lead": lead, "stories": stories, "literature": literature}


def _process_footer(blocks):
    """收尾块：预告 / 反馈 / 报尾（吞掉 `---`，报尾支持正则与位置回退）。"""
    res = {"preview": None, "feedback": None, "colophon": None, "rest": []}
    last_was_hr = False
    for b in blocks:
        role = _block_role(b)
        if role == "preview":
            res["preview"] = b
            last_was_hr = False
        elif role == "feedback":
            res["feedback"] = b
            last_was_hr = False
        elif role == "colophon":
            res["colophon"] = b
            last_was_hr = False
        elif b["type"] == "hr":
            last_was_hr = True  # 报尾前的分隔线吞掉
        else:
            if last_was_hr and res["colophon"] is None and role == "plain":
                res["colophon"] = b  # 位置回退：`---` 后的末段
            else:
                res["rest"].append(b)
            last_was_hr = False
    return res


def build_tree(blocks):
    """扁平块 → 语义文档树（masthead / lede / sections / footer）。"""
    blocks = list(blocks)
    doc = {"masthead": None, "publication_no": None,
           "lede": [], "sections": [], "footer": []}

    for i, b in enumerate(blocks):
        if b["type"] == "h1":
            doc["masthead"] = parse_masthead(b["text"])
            blocks = blocks[i + 1:]
            break

    j = 0
    while j < len(blocks) and blocks[j]["type"] != "h2":
        doc["lede"].append(blocks[j])
        j += 1
    blocks = blocks[j:]

    # 刊号：H1 后的 `刊号：` 行，从导读区提取进报头（不在导读框重复渲染）。
    lede = []
    for b in doc["lede"]:
        if b["type"] == "p" and _block_role(b) == "publication-no":
            doc["publication_no"] = _after_label(b["text"]).strip()
        else:
            lede.append(b)
    doc["lede"] = lede

    i = 0
    while i < len(blocks):
        b = blocks[i]
        if b["type"] == "h2":
            section = {"head": b, "children": [], "footer_started": False}
            i += 1
            while i < len(blocks) and blocks[i]["type"] != "h2":
                role = _block_role(blocks[i])
                # 收尾零件（预告/反馈/报尾）恒进 footer，不进板块；
                # 一旦出现预告/反馈，其后（含报尾前的 `---`）一并进 footer。
                if not section["footer_started"] and role in ("preview", "feedback"):
                    section["footer_started"] = True
                if section["footer_started"] or role in ("preview", "feedback", "colophon"):
                    doc["footer"].append(blocks[i])
                else:
                    section["children"].append(blocks[i])
                i += 1
            section.update(_group_section(section.pop("children")))
            doc["sections"].append(section)
        else:  # 残留顶层块（无 H2 的报告全落 footer）
            doc["footer"].append(b)
            i += 1

    doc["footer"] = _process_footer(doc["footer"])
    return doc


# --------------------------------------------------------------------------- #
# 渲染
# --------------------------------------------------------------------------- #
def _after_label(text):
    """去掉行首「标签：」，返回冒号后的正文。"""
    m = _LABEL_COLON.match(text)
    return text[m.end():] if m else text


def _colophon_body_html(text):
    """AI 撰写说明正文：Agent 工具名 / 模型名用主题绿突出（措辞模板见 SKILL.md）。"""
    html_out = render_inline(text)
    m = _COLOPHON_AGENT.search(text)
    if not m:
        return html_out
    for token, cls in ((m.group(1).strip(), "colophon-tool"),
                       (m.group(2).strip(), "colophon-model")):
        if token:
            html_out = html_out.replace(
                html.escape(token),
                '<span class="{}">{}</span>'.format(cls, html.escape(token)))
    return html_out


def _data_line_html(text):
    m = _LABEL_COLON.match(text)
    if m:
        return ('<li class="data-line"><strong>{}</strong>{}<span>{}</span></li>'
                .format(html.escape(m.group(0)[:-1].strip()),
                        m.group(0)[-1],
                        render_inline(text[m.end():])))
    return '<li class="data-line">{}</li>'.format(render_inline(text))


def _blockquote_html(b):
    lines = b["lines"]
    if len(lines) >= 2 and _QUOTE_ATTR.match(lines[-1].strip()):
        body = "".join("<p>{}</p>".format(render_inline(l)) for l in lines[:-1])
        attr = render_inline(lines[-1].strip())
        return ('<blockquote>{}<footer class="quote-attribution">{}</footer>'
                "</blockquote>".format(body, attr))
    body = "".join("<p>{}</p>".format(render_inline(l)) for l in lines)
    return "<blockquote>{}</blockquote>".format(body)


def _list_html(b, kind):
    """通用列表渲染（支持 2 层嵌套）。"""
    def rec(items, depth):
        out = []
        i = 0
        while i < len(items):
            d, txt = items[i]
            if d < depth:
                break
            if d == depth:
                out.append("<li>{}".format(render_inline(txt)))
                sub = []
                j = i + 1
                while j < len(items) and items[j][0] > depth:
                    sub.append(items[j])
                    j += 1
                if sub:
                    out.append(rec(sub, depth + 1))
                out.append("</li>")
                i = j
            else:
                i += 1
        return "<{}>{}</{}>".format(kind, "".join(out), kind)
    return rec(b["items"], 1)


def _table_html(b):
    rows = b["rows"]
    if not rows:
        return ""
    head = "".join("<th>{}</th>".format(render_inline(c)) for c in rows[0])
    body = "".join(
        "<tr>{}</tr>".format("".join(
            "<td>{}</td>".format(render_inline(c)) for c in r))
        for r in rows[1:])
    return '<table><thead><tr>{}</tr></thead><tbody>{}</tbody></table>'.format(
        head, body)


def block_to_html(b):
    """单个块 → HTML（按角色/类型分发）。"""
    role = _block_role(b)
    t = b["type"]
    if t == "p":
        if role == "dateline":
            return '<p class="dateline">{}</p>'.format(render_inline(b["text"]))
        if role == "source":
            return '<p class="source">{}</p>'.format(render_inline(b["text"]))
        if role == "preview":
            return ('<div class="preview"><span class="label">下期预告</span>'
                    "{}</div>".format(render_inline(_after_label(b["text"]))))
        if role == "feedback":
            return '<p class="feedback">{}</p>'.format(render_inline(b["text"]))
        if role == "colophon":
            return ('<footer class="colophon"><span class="label">AI 撰写说明</span>'
                    "<p>{}</p></footer>".format(
                        _colophon_body_html(_after_label(b["text"]))))
        return "<p>{}</p>".format(render_inline(b["text"]))
    if t == "h2":
        return '<h2 class="section-head">{}</h2>'.format(render_inline(b["text"]))
    if t == "h3":
        return "<h3>{}</h3>".format(render_inline(b["text"]))
    if t == "h4":
        return "<h4>{}</h4>".format(render_inline(b["text"]))
    if t == "ul":
        if role == "event-meta":
            lis = "".join(_data_line_html(txt) for _, txt in b["items"])
            return '<ul class="event-meta">{}</ul>'.format(lis)
        return _list_html(b, "ul")
    if t == "ol":
        if role == "ol":
            lis = "".join("<li>{}</li>".format(render_inline(txt))
                          for _, txt in b["items"])
            return '<ol class="literature-list">{}</ol>'.format(lis)
        return _list_html(b, "ol")
    if t == "blockquote":
        return _blockquote_html(b)
    if t == "table":
        return _table_html(b)
    if t == "pre":
        return "<pre>{}</pre>".format(html.escape("\n".join(b["lines"])))
    if t == "hr":
        return "<hr>"
    return ""


# --------------------------------------------------------------------------- #
# CSS
# --------------------------------------------------------------------------- #
STYLE = r"""
:root{
  --bg:#FCFCFD;          /* 暖白纸面 */
  --ink:#1E1E1C;         /* 墨色（标题/刊头） */
  --ink-soft:#55554F;    /* 正文 */
  --ink-faint:#8A8A84;   /* 弱字（电头/出处/赛事数据） */
  --hairline:#D9D9D8;    /* 发丝线 */
  --hairline-strong:#CFCECB; /* 强线（刊头/表格/分隔） */
  --panel:#F7F7F5;       /* 面板底（导读/引文/代码） */
  --panel-strong:#F0F0EE; /* 面板底（文献块） */
  --accent:#016737;      /* 主题绿：仅做状态与强调，不装饰链接 */
  --accent-soft:#E5F0EA; /* 绿浅底 */
  /* 字栈：--serif（报刊衬线）/ --mono（技术 mono）优先用 <head> 加载的网络字体
     （Noto Serif SC + JetBrains Mono，fonts.googleapis.cn，display:swap）；
     断网或镜像失效时自动落到下方系统字栈，离线仍可读。
     --sans（正文）：西文/数字排在等宽 mono 前（技术质感），中文仍落无衬线——
     等宽字体无 CJK 字形，中文自动落到后续雅黑/苹方等，西文则保持等宽。 */
  --serif:"Noto Serif SC","Source Han Serif SC","Noto Serif CJK SC","Songti SC","STSong","SimSun",Georgia,"Times New Roman",serif;
  --sans:"JetBrains Mono","IBM Plex Mono",ui-monospace,SFMono-Regular,"Cascadia Mono",Consolas,"PingFang SC","Microsoft YaHei","Noto Sans SC","Source Han Sans SC","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif;
  --mono:"JetBrains Mono","IBM Plex Mono",ui-monospace,SFMono-Regular,"Cascadia Mono",Consolas,"Courier New",monospace;
}
*{box-sizing:border-box;border-radius:0}   /* 直角 = 严谨 */
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink-soft);
  font-family:var(--sans);font-size:16px;line-height:1.75;-webkit-font-smoothing:antialiased}
a{color:inherit;text-decoration:underline;text-underline-offset:2px}  /* 暗色下划线，不变绿 */
.report{max-width:46rem;margin:0 auto;padding:2.25rem clamp(1rem,4vw,2.5rem) 3.5rem}

/* 刊头：双线 + 衬线大刊名 */
.masthead{text-align:left;padding:2.5rem 0 1.5rem;border-bottom:3px double var(--ink);margin-bottom:1.75rem}
.masthead .publication-name{font-family:var(--serif);font-weight:700;font-size:3rem;
  letter-spacing:.14em;color:var(--ink);line-height:1.15;margin:0}
.masthead .issue-meta{font-family:var(--mono);font-size:.8125rem;letter-spacing:.25em;
  color:var(--ink-faint);margin:.9rem 0 0}
.masthead .publication-no{font-family:var(--mono);font-size:.6875rem;letter-spacing:.3em;
  color:var(--ink-faint);margin:.5rem 0 0}

/* 导读框：面板 + 左侧绿边；电头右对齐 mono */
.lede{background:var(--panel);border:1px solid var(--hairline);border-left:3px solid var(--accent);
  padding:1.1rem 1.25rem;margin:1.75rem 0}
.lede p{margin:.35rem 0}
.lede .dateline{font-family:var(--mono);font-size:.8125rem;letter-spacing:.12em;
  color:var(--ink-faint);text-align:right;margin-top:.6rem}
.lede .dateline::before{content:"";display:inline-block;width:2em;height:1px;
  background:var(--accent);vertical-align:middle;margin-right:.5em}

/* 版眉：绿竖条 + 标题 + 尾随发丝线 */
.section-head{display:flex;align-items:center;gap:.75rem;font-family:var(--serif);
  font-weight:700;font-size:1.5rem;color:var(--ink);line-height:1.2;margin:3rem 0 1.5rem}
.section-head::before{content:"";width:.45em;height:1.6rem;background:var(--accent);flex:none}
.section-head::after{content:"";flex:1;height:1px;background:var(--hairline)}
section.headline .section-head{font-size:1.75rem}
.kicker{font-family:var(--mono);font-size:.75rem;letter-spacing:.3em;text-transform:uppercase;
  color:var(--accent);background:var(--accent-soft);display:inline-block;padding:.15rem .5rem;margin:0 0 .75rem}

/* 条目：发丝线分隔，衬线标题 */
.section>p{margin:.6rem 0}
.story{margin:0 0 1.75rem;padding-bottom:1.25rem;border-bottom:1px solid var(--hairline)}
.story:last-child{border-bottom:0}
.story h3,.subsection-head{font-family:var(--serif);font-weight:600;color:var(--ink);line-height:1.3}
.story h3{font-size:1.25rem;margin:0 0 .55rem}
.subsection-head{font-size:1.1rem;margin:1.75rem 0 .55rem}
.subsection-head::before{content:"§ ";color:var(--accent);font-family:var(--mono)}
.story p{margin:.5rem 0}

/* 出处 / 赛事数据：mono 弱字 */
p.source{font-family:var(--mono);font-size:.8125rem;color:var(--ink-faint);margin:.6rem 0 0}
p.source a{color:var(--ink)}
ul.event-meta{list-style:none;margin:.75rem 0;padding:0;font-family:var(--mono);
  font-size:.875rem;color:var(--ink-faint)}
ul.event-meta li{margin:.2rem 0;padding-left:0}
ul.event-meta li::before{content:"• ";color:var(--accent);position:static;font-size:1em}
ul.event-meta strong{color:var(--ink);font-weight:600}

/* 通用列表：报刊常用小圆点项目符（主题绿，克制使用），嵌套用空心圈 */
ul,ol{margin:.75rem 0}
ul{list-style:none;padding-left:0}
ul>li{position:relative;padding-left:1.4em;margin:.3rem 0}
ul>li::before{content:"•";position:absolute;left:0;font-size:1em;color:var(--accent)}
ul ul{margin:.3rem 0}
ul ul>li::before{content:"◦";font-size:1em;color:var(--accent)}
ol{padding-left:1.5em}
ol>li{margin:.3rem 0}
ol>li::marker{font-family:var(--mono);font-weight:600;color:var(--ink)}

/* 引文框 */
blockquote{margin:1.5rem 0;padding:.9rem 1.1rem;background:var(--panel);
  border-left:3px solid var(--hairline-strong)}
blockquote p{margin:0}
.quote-attribution{text-align:right;font-size:.875rem;color:var(--ink-faint);margin-top:.55rem}

/* 相关文献 */
.literature{margin:2.25rem 0 0;padding:1.1rem 1.25rem;background:var(--panel-strong);
  border:1px solid var(--hairline);border-top:2px solid var(--ink)}
.literature-head{font-family:var(--serif);font-weight:700;color:var(--ink);margin-bottom:.6rem}
.literature-list{margin:.4rem 0 0;padding-left:1.5rem}
.literature-list li{margin:.35rem 0}
.literature-list a{color:var(--ink)}

/* 预告 / 反馈 / 报尾 */
.preview{margin:2.25rem 0 0;padding:.9rem 1.25rem;background:var(--panel);
  border:1px solid var(--hairline);border-left:3px solid var(--accent)}
.preview .label{display:block;font-family:var(--mono);font-size:.75rem;letter-spacing:.3em;
  text-transform:uppercase;color:var(--accent);margin-bottom:.35rem}
.feedback{text-align:right;font-family:var(--mono);font-size:.8125rem;color:var(--ink-faint);margin:1rem 0 0}
.colophon{margin-top:3rem;padding-top:1.5rem;border-top:3px double var(--ink);
  font-family:var(--mono);font-size:.8125rem;color:var(--ink-faint);line-height:1.7}
.colophon .label{font-family:var(--serif);font-weight:700;color:var(--ink)}
.colophon p{margin:.5rem 0 0}
.colophon .colophon-tool,.colophon .colophon-model{color:var(--accent);font-weight:600}

/* 代码 / 表格 */
code{font-family:var(--mono);font-size:.875em;color:var(--ink);background:var(--panel);padding:.1em .35em}
pre{font-family:var(--mono);font-size:.875rem;line-height:1.6;background:var(--panel);
  border:1px solid var(--hairline);padding:1rem;overflow-x:auto;white-space:pre-wrap}
table{border-collapse:collapse;width:100%;margin:1.25rem 0;font-size:.9rem}
th{font-family:var(--mono);font-weight:600;font-size:.8125rem;letter-spacing:.5px;
  text-transform:uppercase;text-align:left;padding:.4rem 0;border-bottom:1px solid var(--hairline-strong)}
td{padding:.5rem 0;border-bottom:1px solid var(--hairline);vertical-align:top}
hr{border:0;border-top:1px solid var(--hairline-strong);margin:2rem 0}

/* 打印 */
@media print{
  body{background:#fff}
  .report{max-width:none;margin:0;padding:0}
  *{box-shadow:none!important}
  .lede,.literature,blockquote,table,pre,.preview{break-inside:avoid}
  h1,h2,h3,h4{break-after:avoid}
  p{orphans:2;widows:2}
  code{white-space:pre-wrap;background:none;padding:0}
  a{color:inherit;text-decoration:underline}
  .masthead,.colophon{border-color:#000}
}
@page{size:A4;margin:18mm 16mm}
"""


def render_html(doc, title, font_css_url=None):
    """文档树 → 完整 HTML 字符串。"""
    out = []
    out.append("<!DOCTYPE html>")
    out.append('<html lang="zh-CN">')
    out.append("<head>")
    out.append('<meta charset="utf-8">')
    out.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    out.append('<meta name="generator" content="cssec-weekly/md2html.py">')
    out.append("<title>{}</title>".format(html.escape(title)))
    if font_css_url:
        host = urlparse(font_css_url).netloc
        out.append('<link rel="preconnect" href="https://{}">'.format(host))
        if host == "fonts.googleapis.cn":
            out.append('<link rel="preconnect" href="https://fonts.gstatic.cn" crossorigin>')
        out.append('<link rel="stylesheet" href="{}">'.format(
            html.escape(font_css_url, quote=True)))
    out.append("<style>{}</style>".format(STYLE))
    out.append("</head>")
    out.append("<body>")
    out.append('<article class="report">')

    # 刊头
    mh = doc["masthead"] or {}
    out.append('<header class="masthead">')
    out.append('<h1 class="publication-name">{}</h1>'.format(
        html.escape(mh.get("name") or title)))
    meta_parts = []
    if mh.get("issue"):
        meta_parts.append("第 {} 期".format(mh["issue"]))
    if mh.get("range"):
        meta_parts.append(mh["range"])
    if meta_parts:
        out.append('<p class="issue-meta">{}</p>'.format(
            html.escape(" · ".join(meta_parts))))
    if doc["publication_no"]:
        out.append('<p class="publication-no">刊号 {}</p>'.format(
            html.escape(doc["publication_no"])))
    out.append("</header>")

    # 导读
    if doc["lede"]:
        out.append('<section class="lede">')
        for b in doc["lede"]:
            out.append(block_to_html(b))
        out.append("</section>")

    # 板块
    for sec in doc["sections"]:
        is_headline = sec["head"]["text"].lstrip().startswith("本期主题")
        cls = "section" + (" headline" if is_headline else "")
        out.append('<section class="{}">'.format(cls))
        out.append('<h2 class="section-head">{}</h2>'.format(
            render_inline(sec["head"]["text"])))
        if is_headline:
            out.append('<p class="kicker">头条深度报道</p>')
        for b in sec["lead"]:
            out.append(block_to_html(b))
        for st in sec["stories"]:
            if is_headline:
                out.append('<h3 class="subsection-head">{}</h3>'.format(
                    render_inline(st["head"]["text"])))
                for b in st["children"]:
                    out.append(block_to_html(b))
            else:
                out.append('<article class="story">')
                out.append('<h3 class="story-title">{}</h3>'.format(
                    render_inline(st["head"]["text"])))
                for b in st["children"]:
                    out.append(block_to_html(b))
                out.append("</article>")
        for lit in sec["literature"]:
            out.append('<div class="literature">')
            out.append('<div class="literature-head">{}</div>'.format(
                render_inline(lit["head"]["text"])))
            out.append(block_to_html(lit["list"]))
            out.append("</div>")
        out.append("</section>")

    # 收尾
    f = doc["footer"]
    if f["preview"]:
        out.append(block_to_html(f["preview"]))
    if f["feedback"]:
        out.append(block_to_html(f["feedback"]))
    if f["colophon"]:
        out.append(block_to_html(f["colophon"]))
    for b in f["rest"]:
        out.append(block_to_html(b))

    out.append("</article>")
    out.append("</body>")
    out.append("</html>")
    return "\n".join(out) + "\n"


def _default_output(path):
    base, _ = os.path.splitext(path)
    return base + ".html"


def main(argv=None):
    ap = argparse.ArgumentParser(description="周报 Markdown → 自包含报刊风格 HTML")
    ap.add_argument("input", help="输入 Markdown 文件路径")
    ap.add_argument("-o", "--output", default=None,
                    help="输出 HTML 路径（默认：输入同目录同名 .html）")
    ap.add_argument("--title", default=None,
                    help="HTML <title>（默认：H1 刊名）")
    ap.add_argument("--font-css", default=None,
                    help="网络字体 CSS URL（默认：Google Fonts 国内镜像，见常量 FONT_CSS_URL；"
                         "环境变量 CSSEC_FONT_CSS 亦覆盖）。传空字符串 '' 禁用网络字体，用纯系统字栈")
    args = ap.parse_args(argv)

    try:
        text = read_document(args.input)
        if not text.strip():
            print("警告: 输入为空，仍生成最小 HTML 壳", file=sys.stderr)
        doc = build_tree(scan_blocks(text))
        if doc["masthead"]:
            title = args.title or doc["masthead"]["name"]
        else:
            title = args.title or os.path.splitext(os.path.basename(args.input))[0]
        font_css_url = (args.font_css if args.font_css is not None
                        else os.environ.get("CSSEC_FONT_CSS", FONT_CSS_URL))
        out_path = os.path.abspath(args.output or _default_output(args.input))
        parent = os.path.dirname(out_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(out_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_html(doc, title, font_css_url))
        print("已生成: {}".format(out_path))
        return 0
    except Exception as e:  # noqa: BLE001 —— 任何失败都落 stderr + exit 1
        print("错误: {}".format(e), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
