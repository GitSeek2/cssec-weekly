"""推算本期周报的期数与时间范围。

逻辑（对应设计规格 §8 待决项「期数/日期计算」）：
    - 期数：扫 issues/ 下各目录内成品文件名（`CSSEC 周报 · 第 N 期`，
      兼容遗留 `第N期_YYYY-MM-DD`），取最大 N，下一期 = N+1；
      同时兼容历史遗留 `issue-NNN` 目录名。目录为空或不存在则从第 1 期起。
    - 目录名：发刊日（today）驱动的自封刊号 `CSYY-MMWW-TP`（CS=CSSEC 前缀，
      仿 CN 刊号形态），WW 为周一对齐的「当月第几周」；目录名不再编码期号。
    - 时间范围：发刊日为今天，内容覆盖近 `--days` 天（默认 10）。区间 = [今天-days, 今天]。

用法:
    uv run python scripts/issue_meta.py              # 默认近 10 天
    uv run python scripts/issue_meta.py --days 14
    uv run python scripts/issue_meta.py --today 2026-08-05   # 指定发刊日（测试用）

输出 JSON:
    {
      "issue": 2,                       # 本期期号 (int，扫成品文件名取最大 +1)
      "days": 10,                       # 覆盖天数
      "today": "2026-08-10",            # 发刊日
      "start": "2026-07-31",            # 区间起点（含）
      "end": "2026-08-10",              # 区间终点（含）
      "range": "2026-07-31 ~ 2026-08-10",
      "dirname": "CS26-0802-TP",        # 归档目录名（自封刊号 CSYY-MMWW-TP，WW 周一对齐）
      "filename": "CSSEC 周报 · 第 2 期", # 成品文件名 base（不补零；md/html/pdf 共用）
      "existing_max": 1,                # 已存在的最大期号（无则 0）
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

# issues 存档在仓库根目录（非技能目录内）：脚本位于
# <根>/skills/cssec-weekly/scripts/，向上四级才是仓库根。
ISSUES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))))),
    "issues")
# 兼容历史遗留 `issue-NNN` / `issue001` / `issue_001` 目录名（group1），
# 与遗留 `第N期_YYYY-MM-DD` 文件名（group2）。用 search 即可。
_NAME = re.compile(
    r"(?:issue[-_ ]*([0-9]+))|第\s*([0-9]+)\s*期",
    re.UNICODE | re.IGNORECASE)
# 新命名 `CSYY-MMWW-TP` 目录名不含期号：期号从目录内成品文件名
# `CSSEC 周报 · 第 N 期.{md,html,pdf}`（兼容遗留 `第N期_YYYY-MM-DD`）提取。
_FILENAME = re.compile(r"第\s*([0-9]+)\s*期", re.UNICODE)


def dirname_for(today):
    """新命名：自封刊号 `CSYY-MMWW-TP`（CSSEC 玩梗，仿 CN 刊号形态）。

    结构：CS = CSSEC 前缀；YY = 2 位年（占 CN 的省码位，国标里 2X 皆空号，
    自曝假刊）；MMWW = 2 位月 + 周一对齐的当月第几周（0801 = 8 月第 1 周，
    恰落在 CN 报纸号段 0001~0999，而周报正是报纸节奏）；TP = 中图分类
    自动化技术·计算机技术。字典序 == 时间序。

    周一对齐：发刊日所在自然周（周一~周日）在当月排第几；周一落在上月
    则该周记发刊月第 1 周。每周一发刊时 WW 01~05 顺排。
    """
    yy, mm = today.year % 100, today.month
    monday = today - dt.timedelta(days=today.weekday())  # 所在自然周的周一
    ww = 1 if monday.month != today.month else (monday.day - 1) // 7 + 1
    return f"CS{yy:02d}-{mm:02d}{ww:02d}-TP"


def existing_issues(issues_dir=ISSUES_DIR):
    """返回已存期号列表（int），按升序。目录不存在视为空。"""
    out = []
    if not os.path.isdir(issues_dir):
        return out
    for name in os.listdir(issues_dir):
        sub = os.path.join(issues_dir, name)
        if not os.path.isdir(sub):
            continue
        # 新命名：扫目录内成品文件名取期号（`CSSEC 周报 · 第 N 期.md`）。
        try:
            for f in os.listdir(sub):
                m = _FILENAME.search(f)
                if m:
                    out.append(int(m.group(1)))
                    break
        except OSError:
            pass
        # 兼容历史遗留 `issue-NNN` 目录名。
        m2 = _NAME.search(name)
        if m2:
            try:
                out.append(int(m2.group(1) or m2.group(2)))
            except ValueError:
                pass
    return sorted(set(out))


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
        # 命名分工：目录 = 自封刊号（CSYY-MMWW-TP，WW 周一对齐，字典序==时间序）；
        # 文件 = 人类可读标题（CSSEC 周报 · 第 N 期，不补零，md/html/pdf 共用）。
        # 详见 SKILL.md「成品命名规范」。
        "dirname": dirname_for(today),
        "filename": f"CSSEC 周报 · 第 {issue} 期",
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
