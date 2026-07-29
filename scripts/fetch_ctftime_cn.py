"""Hello-CTFtime 国内赛事 (CN.json) 抓取。

结构: {success, data:{result:[...], total, page, size}}
字段: name / link / comp_time_start / comp_time_end / detail
日期: 中文 '2026年07月17日 19:00'

筛选: 赛事结束时间 >= 今天-窗口起点 的视为"即将举办/进行中/近期"；
已结束 (comp_time_end 早于窗口起点) 的过滤掉。无 status 字段。
"""

import argparse

import lib

URL = "https://raw.githubusercontent.com/ProbiusOfficial/Hello-CTFtime/main/CN.json"


def main():
    ap = argparse.ArgumentParser()
    lib.add_window_args(ap)
    args = ap.parse_args()

    errors = []
    try:
        data = lib.http_get_json(URL)
        result = (((data or {}).get("data") or {}).get("result")) or []
    except Exception as e:  # noqa: BLE001
        result, errors = [], [f"ctftime_cn: {type(e).__name__}: {e}"]

    start, _end = lib.resolve_window(args)
    items = []
    for ev in result:
        end = lib.parse_date_cn(ev.get("comp_time_end"))
        # 取起始作为展示日期
        begin = lib.parse_date_cn(ev.get("comp_time_start"))
        # 保留: 结束时间在窗口起点之后（仍在窗口内或尚未结束）
        if not end or end < start:
            continue
        date = begin or end
        items.append(lib.item(
            source="ctftime_cn",
            section_guess="赛事活动",
            title=ev.get("name", ""),
            url=ev.get("link", ""),
            date=date,
            summary="",
            extra={
                "detail": ev.get("detail", ""),
                "comp_time_start": ev.get("comp_time_start", ""),
                "comp_time_end": ev.get("comp_time_end", ""),
                "scope": "国内",
            },
        ))

    lib.emit(items, errors)


if __name__ == "__main__":
    lib.run_main(main)
