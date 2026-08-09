"""CSSEC 周报信息源抓取 - 共享工具库。

仅依赖 Python 标准库（urllib，无需 pip install），保证 skill 零依赖即可运行。

每个 fetch_*.py 脚本输出统一结构的 JSON：
    {"items": [...], "errors": [...]}
条目 item 结构：
    {
      "source":        源标识 (secrss|ctftime_cn|ctftime_global|cac|miit),
      "section_guess": 板块初判 (态势感知|漏洞情报|前沿技术|政策法规|赛事活动|未定),
      "title":         标题,
      "url":           原文/官方链接,
      "date":          发布/赛事日期, 归一化为 YYYY-MM-DD,
      "summary":       一句话摘要 (无则 ""),
      "extra":         源特有字段 dict
    }
"""

import datetime as _dt
import json
import re
import sys
import time
import urllib.request
import urllib.error
import urllib.parse

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


# --------------------------------------------------------------------------- #
# HTTP
# --------------------------------------------------------------------------- #
def http_get(url, *, headers=None, timeout=20, retries=2, encoding=None):
    """GET 一个 URL，返回 (text, status)。失败重试，最终失败抛异常。"""
    hdr = {"User-Agent": UA, "Accept": "*/*"}
    if headers:
        hdr.update(headers)
    req = urllib.request.Request(url, headers=hdr, method="GET")
    last_err = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read()
                status = resp.status
                if encoding:
                    text = raw.decode(encoding, errors="replace")
                else:
                    # 优先用 HTTP header 声明的编码，否则 utf-8
                    charset = resp.headers.get_content_charset() or "utf-8"
                    text = raw.decode(charset, errors="replace")
                return text, status
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
    raise last_err


def http_get_json(url, **kwargs):
    text, _ = http_get(url, **kwargs)
    return json.loads(text)


# --------------------------------------------------------------------------- #
# 日期解析 / 时间窗
# --------------------------------------------------------------------------- #
def today():
    """当前日期（只到天）。供脚本默认计算时间窗使用。"""
    return _dt.date.today()


def window_start(days=10):
    return _dt.date.today() - _dt.timedelta(days=days)


def parse_date_iso(s):
    """解析 'YYYY-MM-DD ...' 形式，返回 date 或 None。"""
    if not s:
        return None
    m = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", str(s))
    if not m:
        return None
    y, mo, d = (int(x) for x in m.groups())
    try:
        return _dt.date(y, mo, d)
    except ValueError:
        return None


def parse_date_cn(s):
    """解析中文日期 '2026年07月17日 19:00'，返回 date 或 None。"""
    if not s:
        return None
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", str(s))
    if not m:
        return parse_date_iso(s)  # 兜底
    y, mo, d = (int(x) for x in m.groups())
    try:
        return _dt.date(y, mo, d)
    except ValueError:
        return None


def in_window(d, days=10):
    """d(date) 是否在 [today-days, today] 内（含端点）。"""
    if d is None:
        return False
    start = window_start(days)
    return start <= d <= _dt.date.today()


# --------------------------------------------------------------------------- #
# 时间窗解析（收敛为单一真相源：issue_meta 输出 start/end，fetch 消费）
# --------------------------------------------------------------------------- #
def last_monday(today=None):
    """返回 today 所在周的"上周一"（date）。

    窗口起点 = 上周一。算法：先找到本周一（today - weekday 天），再往前 7 天。
    若 today 本身就是周一，本周一 = today，上周一 = today - 7 天。
    """
    today = today or _dt.date.today()
    this_monday = today - _dt.timedelta(days=today.weekday())
    return this_monday - _dt.timedelta(days=7)


def in_range(d, start, end):
    """d(date) 是否在 [start, end] 内（含端点）。
    start/end 为 None 表示该侧无界：start=None 无下界，end=None 无上界。
    """
    if d is None:
        return False
    if start is not None and d < start:
        return False
    if end is not None and d > end:
        return False
    return True


def add_window_args(ap, *, default_days=10):
    """给 fetch 脚本的 argparse 加统一时间窗参数。

    优先级（高到低）：--start/--end 显式 > --days rolling。
    典型用法：issue_meta 透传 --start/--end；命令行调试直接 --days。
    """
    ap.add_argument("--days", type=int, default=default_days,
                    help="rolling 窗口天数（不传 --start/--end 时生效，默认 %(default)s）")
    ap.add_argument("--start", default=None,
                    help="窗口起点 YYYY-MM-DD（含），覆盖 --days 逻辑")
    ap.add_argument("--end", default=None,
                    help="窗口终点 YYYY-MM-DD（含），默认今天")


def resolve_window(args):
    """从 argparse 的 args 解析出确定的 (start, end) date。

    规则：
      - 若 args.start 存在：用它作 start，end = args.end 或今天。
        （--start/--end 优先，issue_meta 透传走这条）
      - 否则（仅 --days）：rolling，start = today-days，end = today。
        （降级/调试路径，保持旧行为）
    """
    today = _dt.date.today()
    if getattr(args, "start", None):
        start = _coerce_date(args.start, today)
        end = _coerce_date(args.end, today) if getattr(args, "end", None) else today
        return start, end
    # rolling 降级
    days = getattr(args, "days", 10) or 10
    return window_start(days), today


def _coerce_date(s, default=None):
    """'YYYY-MM-DD' 字符串 -> date；失败返回 default。"""
    try:
        return _dt.date.fromisoformat(s)
    except (ValueError, TypeError):
        return default


def to_iso(d):
    return d.strftime("%Y-%m-%d") if d else ""


# --------------------------------------------------------------------------- #
# 输出
# --------------------------------------------------------------------------- #
def emit(items, errors=None):
    """把统一结构打印到 stdout（AI 读取脚本输出即得到此 JSON）。"""
    payload = {"items": items, "errors": errors or []}
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def item(source, section_guess, title, url, date, summary="", extra=None):
    """构造统一条目。date 接受 date 对象或字符串。"""
    if isinstance(date, (_dt.date, _dt.datetime)):
        date = to_iso(date if isinstance(date, _dt.date) else date.date())
    return {
        "source": source,
        "section_guess": section_guess,
        "title": (title or "").strip(),
        "url": url or "",
        "date": date or "",
        "summary": (summary or "").strip(),
        "extra": extra or {},
    }


def run_main(main_fn):
    """脚本入口包装：捕获异常，失败也输出合法 JSON（errors），不崩。"""
    try:
        main_fn()
    except Exception as e:  # noqa: BLE001
        emit([], [f"{type(e).__name__}: {e}"])
        sys.exit(0)


# --------------------------------------------------------------------------- #
# 小工具：HTML 文本清洗（去标签，折叠空白）
# --------------------------------------------------------------------------- #
_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def strip_tags(html):
    if not html:
        return ""
    text = _TAG.sub(" ", html)
    return _WS.sub(" ", text).strip()


# --------------------------------------------------------------------------- #
# RSS / Atom 解析（供境外英文源 fetch 脚本复用）
# --------------------------------------------------------------------------- #
def parse_date_rfc822(s):
    """解析 RSS pubDate（RFC822，如 'Wed, 30 Jul 2026 14:00:00 GMT'），返回 date 或 None。

    用标准库 email.utils.parsedate_to_datetime；失败回退 parse_date_iso（兼容
    Atom 的 ISO 8601 published/updated，以及纯日期串）。
    """
    if not s:
        return None
    import email.utils as _eu
    try:
        dt = _eu.parsedate_to_datetime(str(s))
        if dt is not None:
            return dt.date()
    except (TypeError, ValueError, OverflowError):
        pass
    return parse_date_iso(s)


def parse_rss(xml_text):
    """解析 RSS 2.0 / Atom feed，返回 [{title, url, date, summary, categories}] 列表。

    - RSS 2.0: channel/item，子元素 title/link/pubDate/description/category
    - Atom:    feed/entry，子元素 title，link 取 href 属性，published/updated，summary/content
    容错：标签缺失返回 ""；日期原样保留（解析交给 parse_date_rfc822）。
    解析失败抛异常，由调用方的 run_main 兜成 errors。
    """
    import xml.etree.ElementTree as _ET
    if not xml_text:
        return []
    root = _ET.fromstring(xml_text)

    def _local(tag):
        """去掉命名空间前缀，如 '{http://...}entry' -> 'entry'。"""
        return tag.split("}", 1)[1] if "}" in tag else tag

    # 收集所有 item（RSS）或 entry（Atom）
    nodes = [el for el in root.iter() if _local(el.tag) in ("item", "entry")]
    out = []
    for it in nodes:
        children = {_local(c.tag): c for c in it}

        def text(*names):
            for n in names:
                el = children.get(n)
                if el is not None and (el.text or "").strip():
                    return (el.text or "").strip()
            return ""

        title = text("title")
        # link：RSS 是元素文本，Atom 是 <link href="..."/>
        link = ""
        if "link" in children:
            lel = children["link"]
            link = (lel.text or "").strip() or (lel.get("href") or "").strip()
        # Atom 可能有多个 link，取 rel=alternate 或第一个 href
        if not link:
            for c in it:
                if _local(c.tag) == "link":
                    href = c.get("href")
                    if href and (c.get("rel") in (None, "alternate")):
                        link = href.strip()
                        break
        date = text("pubDate", "published", "updated", "date", "created")
        summary = text("description", "summary", "content", "subtitle")
        cats = []
        for c in it:
            if _local(c.tag) == "category":
                term = (c.text or c.get("term") or "").strip()
                if term:
                    cats.append(term)
        out.append({
            "title": title,
            "url": link,
            "date": date,
            "summary": summary,
            "categories": cats,
        })
    return out
