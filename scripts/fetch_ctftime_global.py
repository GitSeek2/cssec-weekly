"""Hello-CTFtime 国际赛事 (Global.json) 抓取。

结构: 顶层数组 [ {...}, ... ]  (注意与 CN.json 不同，无 envelope)
字段(中文键): 比赛名称 / 比赛时间 / 比赛链接 / 比赛标志 / 比赛形式 /
              比赛状态 / 比赛权重 / 赛事主办 / 比赛ID
日期: '2026-07-31 15:00:00 - 2026-08-02 15:00:00 UTC+8' (范围串)

筛选:
    - 比赛状态 == 'oncoming' 保留；'past' 过滤。
    - 名称含 'POSTPONED' -> extra.postponed = True。
    - 此外按比赛结束时间(范围串右半)过滤掉早于窗口起点的。
"""

import argparse
import re

import lib

URL = "https://raw.githubusercontent.com/ProbiusOfficial/Hello-CTFtime/main/Global.json"

_CTFTIME_EVENT = re.compile(r"https?://ctftime\.org/event/(\d+)")


def _ctftime_url(ev):
    """从 添加日历 或 比赛ID 推导 CTFTime 赛事详情页链接。

    优先解析 添加日历（https://ctftime.org/event/3372.ics）取事件 ID；
    回退用 比赛ID 直接拼。推导不出返回 None（国内赛事 CN.json 无此字段）。
    """
    cal = ev.get("添加日历", "") or ""
    m = _CTFTIME_EVENT.search(cal)
    if m:
        return f"https://ctftime.org/event/{m.group(1)}"
    cid = (ev.get("比赛ID") or "").strip()
    if cid:
        return f"https://ctftime.org/event/{cid}"
    return None


def _split_range(range_str):
    """'2026-07-31 15:00:00 - 2026-08-02 15:00:00 UTC+8' -> (begin, end) date."""
    parts = re.split(r"\s+-\s+", str(range_str))
    begin = lib.parse_date_iso(parts[0]) if len(parts) >= 1 else None
    end = lib.parse_date_iso(parts[1]) if len(parts) >= 2 else begin
    return begin, end


def main():
    ap = argparse.ArgumentParser()
    lib.add_window_args(ap)
    args = ap.parse_args()

    errors = []
    try:
        data = lib.http_get_json(URL)
        events = data if isinstance(data, list) else []
    except Exception as e:  # noqa: BLE001
        events, errors = [], [f"ctftime_global: {type(e).__name__}: {e}"]

    start, _end = lib.resolve_window(args)
    items = []
    for ev in events:
        status = ev.get("比赛状态", "")
        name = ev.get("比赛名称", "")
        # 过滤已结束
        if status and status != "oncoming":
            continue
        begin, end = _split_range(ev.get("比赛时间", ""))
        # 已早于窗口起点的也过滤
        if end and end < start:
            continue
        items.append(lib.item(
            source="ctftime_global",
            section_guess="赛事活动",
            title=name,
            url=ev.get("比赛链接", ""),
            date=begin or end,
            summary="",
            extra={
                "scope": "国际",
                "form": ev.get("比赛形式", ""),
                "logo": ev.get("比赛标志", ""),
                "weight": ev.get("比赛权重", ""),
                "organizer": ev.get("赛事主办", ""),
                "status": status,
                "time_range": ev.get("比赛时间", ""),
                "postponed": "POSTPONED" in name.upper(),
                "calendar": ev.get("添加日历", ""),
                "ctftime_url": _ctftime_url(ev),
            },
        ))

    lib.emit(items, errors)


if __name__ == "__main__":
    lib.run_main(main)
