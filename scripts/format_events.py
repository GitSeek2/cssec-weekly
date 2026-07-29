"""赛事活动板块 Markdown 生成器。

把 Hello-CTFtime（CN.json / Global.json）的赛事数据，格式化成可直接粘贴进
周报「赛事活动」板块的 Markdown 片段（信息行式）。消除每期发刊时手工拼时间、
拼链接的重复劳动。

做的事：
    1. 推导 CTFTime 赛事详情页链接（国际赛事）：从 添加日历 / 比赛ID 得
       https://ctftime.org/event/<id>。国内赛事无 ID，只给官网链接。
    2. 把竞赛时间格式化为带 UTC+8 的日期范围：
       - 国际：'2026-07-31 15:00:00 - 2026-08-02 15:00:00 UTC+8' -> '2026-07-31 ~ 2026-08-02（UTC+8）'
       - 国内：comp_time_start/comp_time_end（'2026年07月17日 19:00'）-> '2026-07-17 ~ 2026-07-19（UTC+8）'
       同日起止的输出单日。
    3. 输出每个赛事一段 Markdown（H3 + 一句话点睛占位 + 竞赛时间/链接两行）。

用法:
    uv run python scripts/format_events.py --start 2026-07-19 --end 2026-07-29
    uv run python scripts/format_events.py --start <start> --end <end> --json   # 兼容信息池记录

输出:
    - 默认：拼好的 Markdown 片段（撰写时整段粘贴，再润色「一句话点睛」、删不采纳的赛事）。
    - --json：仍输出统一 {items, errors}，每条 extra 补 ctftime_url / formatted_time_range。

零外部依赖（仅标准库 + 同目录 lib）。
"""

import argparse
import re

import lib

CN_URL = "https://raw.githubusercontent.com/ProbiusOfficial/Hello-CTFtime/main/CN.json"
GLOBAL_URL = "https://raw.githubusercontent.com/ProbiusOfficial/Hello-CTFtime/main/Global.json"

_CTFTIME_EVENT = re.compile(r"https?://ctftime\.org/event/(\d+)")


# --------------------------------------------------------------------------- #
# CTFTime 链接推导（与 fetch_ctftime_global 保持一致）
# --------------------------------------------------------------------------- #
def ctftime_url_global(ev):
    cal = ev.get("添加日历", "") or ""
    m = _CTFTIME_EVENT.search(cal)
    if m:
        return f"https://ctftime.org/event/{m.group(1)}"
    cid = (ev.get("比赛ID") or "").strip()
    if cid:
        return f"https://ctftime.org/event/{cid}"
    return None


# --------------------------------------------------------------------------- #
# 时间范围格式化
# --------------------------------------------------------------------------- #
def _fmt_date(d):
    """date -> 'YYYY-MM-DD'；None -> ''。"""
    return lib.to_iso(d) if d else ""


def _split_range(range_str):
    """'2026-07-31 15:00:00 - 2026-08-02 15:00:00 UTC+8' -> (begin, end) date。"""
    parts = re.split(r"\s+-\s+", str(range_str))
    begin = lib.parse_date_iso(parts[0]) if len(parts) >= 1 else None
    end = lib.parse_date_iso(parts[1]) if len(parts) >= 2 else begin
    return begin, end


def time_range_global(ev):
    """国际赛事：取 比赛时间 的日期范围，标 UTC+8（数据源本身带 UTC+8）。"""
    begin, end = _split_range(ev.get("比赛时间", ""))
    if not begin and not end:
        return ""
    if begin and end and begin == end:
        return f"{_fmt_date(begin)}（UTC+8）"
    return f"{_fmt_date(begin) or '?'} ~ {_fmt_date(end) or '?'}（UTC+8）"


def time_range_cn(ev):
    """国内赛事：comp_time_start ~ comp_time_end，默认 UTC+8（国内赛事）。"""
    begin = lib.parse_date_cn(ev.get("comp_time_start", ""))
    end = lib.parse_date_cn(ev.get("comp_time_end", ""))
    if not begin and not end:
        return ""
    if begin and end and begin == end:
        return f"{_fmt_date(begin)}（UTC+8）"
    return f"{_fmt_date(begin) or '?'} ~ {_fmt_date(end) or '?'}（UTC+8）"


# --------------------------------------------------------------------------- #
# 抓取 + 过滤（与 fetch_ctftime_*.py 同口径，保证时间窗一致）
# --------------------------------------------------------------------------- #
def fetch_global(start):
    errors = []
    try:
        events = lib.http_get_json(GLOBAL_URL)
        events = events if isinstance(events, list) else []
    except Exception as e:  # noqa: BLE001
        events, errors = [], [f"ctftime_global: {type(e).__name__}: {e}"]
    out = []
    for ev in events:
        status = ev.get("比赛状态", "")
        name = ev.get("比赛名称", "")
        if status and status != "oncoming":
            continue
        _begin, end = _split_range(ev.get("比赛时间", ""))
        if end and end < start:
            continue
        out.append(ev)
    return out, errors


def fetch_cn(start):
    errors = []
    try:
        data = lib.http_get_json(CN_URL)
        result = (((data or {}).get("data") or {}).get("result")) or []
    except Exception as e:  # noqa: BLE001
        result, errors = [], [f"ctftime_cn: {type(e).__name__}: {e}"]
    out = []
    for ev in result:
        end = lib.parse_date_cn(ev.get("comp_time_end"))
        if not end or end < start:
            continue
        out.append(ev)
    return out, errors


# --------------------------------------------------------------------------- #
# Markdown 渲染
# --------------------------------------------------------------------------- #
def _clean_name(name):
    """标题里去掉 ' - POSTPONED' 之类尾注，延期在标题后另行标注。"""
    name = re.sub(r"\s*[-—]\s*POSTPONED\s*$", "", str(name), flags=re.IGNORECASE)
    name = re.sub(r"\s*POSTPONED\s*$", "", name, flags=re.IGNORECASE)
    return name.strip()


def _postponed(ev):
    return "POSTPONED" in (ev.get("比赛名称", "") or "").upper()


def _organizer_name(raw):
    """'CSSA (https://ctftime.org/team/133080)' -> 'CSSA'。去掉尾部括号 URL。"""
    if not raw:
        return ""
    return re.sub(r"\s*\(https?://[^)]*\)\s*$", "", str(raw)).strip()


def _md_link(text, url):
    if url:
        return f"[{text}]({url})"
    return text or ""


def render_global(ev):
    name = _clean_name(ev.get("比赛名称", ""))
    title = f"{name}（已延期）" if _postponed(ev) else name
    official = ev.get("比赛链接", "") or ""
    ctftime = ctftime_url_global(ev)
    tr = time_range_global(ev)

    links = []
    if official:
        links.append(_md_link("官网", official))
    if ctftime:
        links.append(_md_link("CTFtime", ctftime))
    link_line = " · ".join(links) if links else "（无链接）"

    lines = [f"### {title}", ""]
    # 一句话点睛占位：把已知的赛制/权重/主办拼上，撰写时润色
    bits = []
    if ev.get("赛事主办"):
        bits.append(_organizer_name(ev["赛事主办"]))
    if ev.get("比赛形式"):
        bits.append(f"{ev['比赛形式'].strip()} 赛制")
    if ev.get("比赛权重"):
        w = str(ev["比赛权重"]).strip()
        if w and w != "0" and w != "0.00":
            bits.append(f"CTFtime 权重 {w}")
    if _postponed(ev):
        bits.append("原定时间如下，新日期未公布")
    if bits:
        lines.append("，".join(bits) + "。")
        lines.append("")
    lines.append(f"- 竞赛时间：{tr or '见官网'}")
    lines.append(f"- 链接：{link_line}")
    return "\n".join(lines)


def render_cn(ev):
    name = (ev.get("name") or "").strip()
    title = name
    official = ev.get("link", "") or ""
    tr = time_range_cn(ev)
    detail = (ev.get("detail") or "").strip()

    lines = [f"### {title}", ""]
    if detail:
        lines.append(f"{detail}。")
        lines.append("")
    lines.append(f"- 竞赛时间：{tr or '见官网'}")
    lines.append(f"- 链接：{_md_link('官网', official) if official else '（无链接）'}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="赛事活动板块 Markdown 生成器")
    lib.add_window_args(ap)
    ap.add_argument("--json", action="store_true",
                    help="输出统一 {items, errors} JSON（默认输出 Markdown 片段）")
    args = ap.parse_args()

    start, _end = lib.resolve_window(args)

    g_events, g_errors = fetch_global(start)
    cn_events, cn_errors = fetch_cn(start)
    errors = g_errors + cn_errors

    if args.json:
        items = []
        for ev in g_events:
            items.append(lib.item(
                source="ctftime_global", section_guess="赛事活动",
                title=_clean_name(ev.get("比赛名称", "")),
                url=ev.get("比赛链接", ""),
                date=lib.to_iso(_split_range(ev.get("比赛时间", ""))[0]),
                summary="",
                extra={
                    "scope": "国际",
                    "time_range": time_range_global(ev),
                    "ctftime_url": ctftime_url_global(ev),
                    "postponed": _postponed(ev),
                    "weight": ev.get("比赛权重", ""),
                    "form": ev.get("比赛形式", ""),
                    "organizer": ev.get("赛事主办", ""),
                },
            ))
        for ev in cn_events:
            items.append(lib.item(
                source="ctftime_cn", section_guess="赛事活动",
                title=(ev.get("name") or "").strip(),
                url=ev.get("link", ""),
                date=lib.to_iso(lib.parse_date_cn(ev.get("comp_time_start"))),
                summary="",
                extra={
                    "scope": "国内",
                    "time_range": time_range_cn(ev),
                    "detail": ev.get("detail", ""),
                },
            ))
        lib.emit(items, errors)
        return

    # 默认：Markdown 片段
    out = []
    if g_events:
        out.append("<!-- 国际赛事 -->")
        for ev in g_events:
            out.append(render_global(ev))
            out.append("")  # 段间空行
    if cn_events:
        if out:
            out.append("")
        out.append("<!-- 国内赛事 -->")
        for ev in cn_events:
            out.append(render_cn(ev))
            out.append("")
    print("\n".join(out).strip())
    if errors:
        print("\n<!-- 抓取错误：")
        for e in errors:
            print(f"  {e}")
        print("-->")


if __name__ == "__main__":
    lib.run_main(main)
