"""安全内参 (secrss.com) 文章抓取。

本报主内容来源。JSON API，游标翻页控制只取近 N 天。

用法:
    python scripts/fetch_secrss.py                 # 近 10 天全部文章
    python scripts/fetch_secrss.py --days 7
    python scripts/fetch_secrss.py --author 公安部网安局   # 指定作者（走全量+客户端过滤）

说明:
    - 默认模式：用 lastPublishedAt 游标翻页，取发布时间 > today-days 的文章。
    - author 模式：API 传 author 后忽略游标、返回该作者全量流（~79 条上限），
      客户端按 published_at 过滤时间窗。
"""

import argparse
import datetime as dt

import lib

API = "https://www.secrss.com/api/articles"


def _articles(params):
    qs = "&".join(f"{k}={lib.urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{API}?{qs}"
    data = lib.http_get_json(url)
    # 包络: {code:"10000", msg:"操作成功", data:[...]}
    if isinstance(data, dict):
        return data.get("data") or []
    return data or []


def _section_guess(art):
    """按 industryTag / tags / title 关键词粗判板块。判不准返回 '未定'。"""
    text = " ".join(
        [
            str(art.get("title", "")),
            str(art.get("summary", "")),
            str((art.get("industryTag") or {}).get("title", "")),
            " ".join(t.get("title", "") for t in (art.get("tags") or [])),
        ]
    )
    rules = [
        ("赛事活动", ["ctf", "夺旗", "竞赛", "大赛", "决赛", "初赛"]),
        ("漏洞情报", ["cve", "漏洞", "0day", "zero-day", "补丁", "rce", "未授权"]),
        ("前沿技术", ["ai", "大模型", "llm", "人工智能", "机器学习", "深度伪造"]),
        ("政策法规", ["法规", "条例", "监管", "合规", "政策", "办法", "规定", "标准"]),
    ]
    low = text.lower()
    for section, kws in rules:
        if any(k in low for k in (k.lower() for k in kws)):
            return section
    # 态势感知作为默认兜底（数据泄露/攻击事件是最常见类型）
    if any(k in low for k in ["泄露", "攻击", "入侵", "勒索", "apt", "数据窃", "钓鱼"]):
        return "态势感知"
    return "未定"


def _to_item(art):
    pub = lib.parse_date_iso(art.get("published_at") or art.get("humansPublishedAt"))
    url = art.get("source_url") or ""
    if not url:
        url = f"https://www.secrss.com/articles/{art.get('id')}"
    return lib.item(
        source="secrss",
        section_guess=_section_guess(art),
        title=art.get("title", ""),
        url=url,
        date=pub,
        summary=lib.strip_tags(art.get("summary", ""))[:200],
        extra={
            "author": art.get("author", ""),
            "published_at": art.get("published_at", ""),
        },
    )


def fetch_default(start, *, today=None, max_pages=None):
    """游标翻页，取 published_at >= start 的文章。
    start: 窗口起点 date。max_pages: 翻页上限，默认按窗口跨度估算。"""
    today = today or lib.today()
    if max_pages is None:
        span_days = max((today - start).days, 1)
        max_pages = span_days * 2 + 4   # 每页约 0.5~1 天，2 页/天 + 4 缓冲
    # 游标从"现在"开始，逐页取更早的文章，直到越过窗口起点
    cursor = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    out = []
    seen = set()
    for _ in range(max_pages):
        batch = _articles({"lastPublishedAt": cursor, "referer": "web"})
        if not batch:
            break
        oldest = None
        for art in batch:
            d = lib.parse_date_iso(art.get("published_at"))
            if d and d >= start:
                aid = art.get("id")
                if aid not in seen:
                    seen.add(aid)
                    out.append(_to_item(art))
            if d and (oldest is None or d < oldest):
                oldest = d
        # 该批最旧已早于窗口起点 -> 收尾
        if oldest is None or oldest < start:
            break
        cursor = f"{oldest.isoformat()} 00:00:00"
    return out


def fetch_author(author, start):
    """author 模式：API 忽略游标，返回全量；客户端过滤时间窗。"""
    batch = _articles({"author": author, "referer": "web"})
    out = []
    seen = set()
    for art in batch:
        d = lib.parse_date_iso(art.get("published_at"))
        if d and d >= start and art.get("id") not in seen:
            seen.add(art.get("id"))
            it = _to_item(art)
            it["section_guess"] = "政策法规"  # 网安局口径多为监管/通报
            out.append(it)
    return out


def main():
    ap = argparse.ArgumentParser()
    lib.add_window_args(ap)
    ap.add_argument("--author", default=None, help="指定作者，如 公安部网安局")
    args = ap.parse_args()

    start, _end = lib.resolve_window(args)
    errors = []
    try:
        if args.author:
            items = fetch_author(args.author, start)
        else:
            items = fetch_default(start)
    except Exception as e:  # noqa: BLE001
        items, errors = [], [f"secrss: {type(e).__name__}: {e}"]

    lib.emit(items, errors)


if __name__ == "__main__":
    lib.run_main(main)
