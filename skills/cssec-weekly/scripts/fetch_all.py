"""全源聚合采集器 —— 一条命令跑完周报全部信息源。

替代手工逐个执行 11 个 fetch_*.py 的工作（SKILL.md 阶段二）：
    1. 依次执行全部抓取脚本（secrss 主源 + 公安部网安局作者流 + ctftime
       cn/global + cac + miit + thn/bc/krebs/darkreading/schneier）。
    2. 境外英文源代理统一处理：地址读环境变量 CSSEC_PROXY（默认
       http://127.0.0.1:7897），只对英文源子进程注入 HTTPS_PROXY/HTTP_PROXY，
       国内源直连。代理是唯一配置点，不再散落各文档。
    3. 每源原始 JSON 落盘 issues/<dirname>/sources/raw/<源名>.json
       （统一 raw 存档政策：lint.py 链接追溯 / check_facts.py 的语料）。
    4. 合并全部 items 生成 sources/信息池草稿.md —— 按 section_guess/日期
       排序的表格，采纳列留空，供语义去重与选材（LLM 判断类工作）。
    5. 跑 format_events.py 生成 sources/赛事条目草稿.md（信息行式 Markdown，
       撰写赛事板块时直接取用）。

退出码：主内容来源（secrss）0 条或全部源失败时退出 1（单源失败不阻塞，
但 stdout 汇总里显式列出失败源）。

用法:
    uv run python scripts/fetch_all.py --start 2026-08-14 --end 2026-08-24 --dirname CS26-0804-TP
    uv run python scripts/fetch_all.py --days 10 --dirname CS26-0804-TP
    uv run python scripts/fetch_all.py --start … --end … --raw-dir /tmp/raw   # 只落 raw 不建草稿
    uv run python scripts/fetch_all.py --only secrss,thn …                    # 调试单源
"""

import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lib  # noqa: E402

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(SCRIPTS_DIR)))

# (源名, 脚本, 额外参数, 是否走代理)
SOURCES = [
    ("secrss", "fetch_secrss.py", [], False),
    ("secrss_mps", "fetch_secrss.py", ["--author", "公安部网安局"], False),
    ("ctftime_cn", "fetch_ctftime_cn.py", [], False),
    ("ctftime_global", "fetch_ctftime_global.py", [], False),
    ("cac", "fetch_cac.py", [], False),
    ("miit", "fetch_miit.py", [], False),
    ("thn", "fetch_thn.py", [], True),
    ("bleepingcomputer", "fetch_bleepingcomputer.py", [], True),
    ("krebs", "fetch_krebs.py", [], True),
    ("darkreading", "fetch_darkreading.py", [], True),
    ("schneier", "fetch_schneier.py", [], True),
]

SECTION_ORDER = ["态势感知", "漏洞情报", "前沿技术", "政策法规", "赛事活动", "未定"]


def run_fetch(name, script, extra_args, start, end, proxy):
    """跑一个 fetch 脚本，返回 (items, errors)。失败不抛异常。"""
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, script),
           "--start", start, "--end", end] + extra_args
    env = dict(os.environ)
    if proxy:
        env["HTTPS_PROXY"] = proxy
        env["HTTP_PROXY"] = proxy
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=180, env=env, encoding="utf-8")
        payload = json.loads(proc.stdout)
        return payload.get("items") or [], payload.get("errors") or []
    except Exception as e:  # noqa: BLE001 —— 单源失败不阻塞
        return [], ["{}: {}".format(type(e).__name__, e)]


def run_events_md(start, end):
    """format_events.py 的 Markdown 输出（赛事条目草稿），失败返回 None。"""
    cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "format_events.py"),
           "--start", start, "--end", end]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=120, encoding="utf-8")
        return proc.stdout if proc.returncode == 0 and proc.stdout.strip() else None
    except Exception:  # noqa: BLE001
        return None


def _cell(s, limit=60):
    """表格单元格：去竖线/换行，截断。"""
    s = re.sub(r"[|\n\r]", " ", str(s or "")).strip()
    return s if len(s) <= limit else s[: limit - 1] + "…"


def render_pool_draft(all_items):
    """items → 信息池草稿.md（按板块分组、组内按日期倒序的表格）。"""
    lines = ["# 信息池草稿（fetch_all 自动生成）", "",
             "> 由 `fetch_all.py` 生成的原始候选池。接下来做语义去重与选材：",
             "> 同一事件多源合并（英文一手链接优先）、剔除企业自宣与低密度信息，",
             "> 每行填「是否采纳 + 理由」，定稿为 `信息池.md`。表格里的表态句原话",
             "> 保留在摘要列——简讯引语从这取。", ""]
    if not all_items:
        lines.append("（空）")
        return "\n".join(lines) + "\n"
    groups = {}
    for it in all_items:
        sec = it.get("section_guess") or "未定"
        groups.setdefault(sec, []).append(it)
    for sec in SECTION_ORDER:
        items = groups.get(sec)
        if not items:
            continue
        items.sort(key=lambda x: x.get("date") or "", reverse=True)
        lines.append("## {}".format(sec))
        lines.append("")
        lines.append("| 标题 | 来源 | 日期 | URL | 摘要 | 采纳 |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for it in items:
            lines.append("| {} | {} | {} | {} | {} |  |".format(
                _cell(it.get("title"), 48), _cell(it.get("source")),
                _cell(it.get("date")), _cell(it.get("url"), 70),
                _cell(it.get("summary"))))
        lines.append("")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description="全源聚合采集器（SKILL.md 阶段二）")
    lib.add_window_args(ap)
    ap.add_argument("--dirname", default=None,
                    help="本期归档目录名（如 CS26-0804-TP）；缺省时只打印结果不落盘")
    ap.add_argument("--raw-dir", default=None,
                    help="raw 存档目录（默认 issues/<dirname>/sources/raw）")
    ap.add_argument("--only", default=None,
                    help="只跑指定源（逗号分隔，如 secrss,thn）——调试用")
    ap.add_argument("--skip-proxy", action="store_true",
                    help="英文源也不走代理（本机可直连时用）")
    args = ap.parse_args()

    start, end = lib.resolve_window(args)
    start_s, end_s = lib.to_iso(start), lib.to_iso(end)
    proxy = None if args.skip_proxy else os.environ.get(
        "CSSEC_PROXY", "http://127.0.0.1:7897")

    sources = SOURCES
    if args.only:
        keep = {s.strip() for s in args.only.split(",")}
        sources = [s for s in SOURCES if s[0] in keep]

    raw_dir = args.raw_dir
    if raw_dir is None and args.dirname:
        raw_dir = os.path.join(REPO_ROOT, "issues", args.dirname, "sources", "raw")
    if raw_dir:
        os.makedirs(raw_dir, exist_ok=True)

    print("fetch_all: 窗口 {} ~ {}{}".format(
        start_s, end_s, "，代理 {}".format(proxy) if proxy else "，不走代理"))
    all_items, failed, counts = [], [], {}
    for name, script, extra, use_proxy in sources:
        items, errors = run_fetch(name, script, extra, start_s, end_s,
                                  proxy if use_proxy else None)
        counts[name] = len(items)
        all_items.extend(items)
        status = "{} 条".format(len(items))
        if errors:
            failed.append((name, errors))
            status += "，errors: {}".format("; ".join(errors)[:120])
        if raw_dir:
            payload = json.dumps({"items": items, "errors": errors},
                                 ensure_ascii=False, indent=2)
            with open(os.path.join(raw_dir, "{}.json".format(name)), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(payload + "\n")
        print("  [{:<16}] {}".format(name, status))

    events_md = None
    if args.dirname:
        events_md = run_events_md(start_s, end_s)
        if events_md and raw_dir:
            src_dir = os.path.dirname(raw_dir)
            with open(os.path.join(src_dir, "赛事条目草稿.md"), "w",
                      encoding="utf-8", newline="\n") as f:
                f.write(events_md)
            print("  [{:<16}] 赛事条目草稿.md 已生成".format("format_events"))

    if args.dirname and raw_dir:
        draft_path = os.path.join(os.path.dirname(raw_dir), "信息池草稿.md")
        with open(draft_path, "w", encoding="utf-8", newline="\n") as f:
            f.write(render_pool_draft(all_items))
        print("  [{:<16}] 信息池草稿.md（{} 条）".format("pool", len(all_items)))

    print("=" * 56)
    print("汇总：{} 源，{} 条候选，失败 {} 源".format(
        len(sources), len(all_items), len(failed)))
    for name, errors in failed:
        print("  失败: {} —— {}".format(name, "; ".join(errors)[:160]))

    secrss_ok = counts.get("secrss", 0) > 0
    all_failed = len(failed) == len(sources)
    if not secrss_ok or all_failed:
        print("错误：{}——停下来向用户报告网络/代理问题，不要继续。".format(
            "主内容来源（secrss）0 条" if not secrss_ok else "全部源失败"))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
