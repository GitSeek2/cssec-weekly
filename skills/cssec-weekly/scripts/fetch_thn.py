"""The Hacker News (thehackernews.com) RSS 抓取。境外英文事件流常驻源。

高产（单次拉取约 50 条），覆盖 CVE / 勒索 / APT / 数据泄露 / 攻击事件。
RSS 2.0 via feedburner，结构标准，无需翻页——一次拉全量，客户端按时间窗过滤。

需走代理（urllib 自动读 HTTP_PROXY/HTTPS_PROXY 环境变量）：
    export HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897

用法:
    uv run python scripts/fetch_thn.py --days 10
    uv run python scripts/fetch_thn.py --start 2026-07-19 --end 2026-07-29
"""

import argparse

import lib

FEED = "https://feeds.feedburner.com/TheHackersNews"
SOURCE = "thn"


def _section_guess(e):
    """按 title/summary/categories 英文关键词粗判板块。判不准返回 '未定'。"""
    text = (str(e.get("title", "")) + " " + str(e.get("summary", "")) + " "
            + " ".join(e.get("categories") or [])).lower()
    rules = [
        ("赛事活动", ["ctf", "capture the flag", "hackathon", "cybercompetition"]),
        ("漏洞情报", ["cve-", "vulnerability", "0-day", "zero-day", "rce",
                    "remote code", "patch", "flaw", "exploit", "backdoor"]),
        ("政策法规", ["law", "regulation", "fine", "fined", "gdpr", "compliance",
                    "ban", "sentenced", "indicted", "sanction"]),
        ("前沿技术", [" ai ", "ai-", "llm", "large language", "machine learning",
                    "deepfake", "chatgpt", "ransomware-as-a-service"]),
    ]
    for section, kws in rules:
        if any(k in text for k in kws):
            return section
    if any(k in text for k in ["breach", "leak", "ransomware", "apt ", "attack",
                               "phishing", "malware", "hacked", "compromise"]):
        return "态势感知"
    return "未定"


def _to_item(e):
    d = lib.parse_date_rfc822(e.get("date"))
    return lib.item(
        source=SOURCE,
        section_guess=_section_guess(e),
        title=e.get("title", ""),
        url=e.get("url", ""),
        date=d,
        summary=lib.strip_tags(e.get("summary", ""))[:200],
        extra={"lang": "en", "categories": e.get("categories") or []},
    )


def main():
    ap = argparse.ArgumentParser()
    lib.add_window_args(ap)
    args = ap.parse_args()

    start, end = lib.resolve_window(args)
    errors = []
    items = []
    try:
        text, _ = lib.http_get(FEED)
        for e in lib.parse_rss(text):
            d = lib.parse_date_rfc822(e.get("date"))
            if lib.in_range(d, start, end):
                items.append(_to_item(e))
    except Exception as ex:  # noqa: BLE001
        errors = [f"{SOURCE}: {type(ex).__name__}: {ex}"]

    lib.emit(items, errors)


if __name__ == "__main__":
    lib.run_main(main)
