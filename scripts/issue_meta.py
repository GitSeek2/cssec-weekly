"""推算本期周报的期数与时间范围。

逻辑（对应设计规格 §8 待决项「期数/日期计算」）：
    - 期数：扫描 issues/ 目录下已有的 `第N期_YYYY-MM-DD`（目录形态，含 周报.md + sources/），
      取最大 N，下一期 = N+1；目录为空或不存在则从第 1 期起。
      正则用 search，同时兼容历史扁平文件 `第N期_YYYY-MM-DD.md`，向后兼容。
    - 时间范围：发刊日为今天，内容覆盖近 `--days` 天（默认 10）。区间 = [今天-days, 今天]。

用法:
    uv run python scripts/issue_meta.py              # 默认近 10 天
    uv run python scripts/issue_meta.py --days 14
    uv run python scripts/issue_meta.py --today 2026-08-05   # 指定发刊日（测试用）

输出 JSON:
    {
      "issue": 7,                       # 本期期号 (int)
      "days": 10,                       # 覆盖天数
      "today": "2026-07-29",            # 发刊日
      "start": "2026-07-19",            # 区间起点（含）
      "end": "2026-07-29",              # 区间终点（含）
      "range": "2026-07-19 ~ 2026-07-29",
      "filename": "第7期_2026-07-29",    # 建议的成品目录名（成品写入该目录下 周报.md）
      "existing_max": 6,                # 已存在的最大期号（无则 0）
      "errors": []
    }
"""

import argparse
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

# 与 fetch_*.py 同级的 issues 目录（脚本位于 scripts/，issues 在上一级）
ISSUES_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "issues")
# 匹配 第N期_YYYY-MM-DD（N 为数字；允许全角/半角数字与期号两侧空格）。
# 用 search，对目录名 `第N期_YYYY-MM-DD` 与历史扁平文件 `第N期_YYYY-MM-DD.md` 都能匹配期号组。
_NAME = re.compile(r"第\s*([0-9]+)\s*期[_\s]*(?:(\d{4}-\d{1,2}-\d{1,2}))?", re.UNICODE)


def existing_issues(issues_dir=ISSUES_DIR):
    """返回已存期号列表（int），按升序。目录不存在视为空。"""
    out = []
    if not os.path.isdir(issues_dir):
        return out
    for name in os.listdir(issues_dir):
        m = _NAME.search(name)
        if m:
            try:
                out.append(int(m.group(1)))
            except ValueError:
                pass
    return sorted(out)


def compute(today=None, days=10, mode="rolling", issues_dir=ISSUES_DIR,
            override_start=None, override_end=None):
    today = today or dt.date.today()
    if isinstance(today, str):
        today = dt.date.fromisoformat(today)

    # 窗口计算（优先级：override > lastweek > rolling）
    if override_start:
        start = dt.date.fromisoformat(override_start)
        end = dt.date.fromisoformat(override_end) if override_end else today
        effective_days = (end - start).days + 1   # 含端点
        mode_label = "override"
    elif mode == "lastweek":
        start = lib.last_monday(today)            # 上周一
        end = today                                # 今天（含）
        effective_days = (end - start).days + 1
        mode_label = "lastweek"
    else:  # rolling（默认，保持旧行为）
        start = today - dt.timedelta(days=days)
        end = today
        effective_days = days + 1
        mode_label = "rolling"
    existing = existing_issues(issues_dir)
    existing_max = max(existing) if existing else 0
    issue = existing_max + 1
    return {
        "issue": issue,
        "days": effective_days,                    # 实际跨度天数（含端点）
        "mode": mode_label,                        # 窗口来源：rolling | lastweek | override
        "today": today.isoformat(),
        "start": start.isoformat(),
        "end": end.isoformat(),
        "range": f"{start.isoformat()} ~ {end.isoformat()}",
        "filename": f"第{issue}期_{today.isoformat()}",
        "existing_max": existing_max,
        "errors": [],
    }


def main():
    ap = argparse.ArgumentParser(description="推算本期周报期数与时间范围")
    ap.add_argument("--days", type=int, default=10,
                    help="rolling 模式覆盖天数（默认 10）")
    ap.add_argument("--mode", choices=["rolling", "lastweek"], default="rolling",
                    help="窗口对齐方式：rolling=当天往前 N 天；lastweek=上周一~今天")
    ap.add_argument("--today", default=None, help="发刊日 YYYY-MM-DD（默认今天，测试用）")
    ap.add_argument("--start", default=None, help="调试：强制窗口起点 YYYY-MM-DD")
    ap.add_argument("--end", default=None, help="调试：强制窗口终点 YYYY-MM-DD")
    ap.add_argument("--issues-dir", default=ISSUES_DIR, help="成品存档目录")
    args = ap.parse_args()
    print(json.dumps(compute(args.today, args.days, args.mode, args.issues_dir,
                             args.start, args.end),
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
