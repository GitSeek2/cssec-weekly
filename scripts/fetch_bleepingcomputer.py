"""BleepingComputer (bleepingcomputer.com) RSS 抓取。境外英文深度源。

深度报道为主，常含厂商博客 / PoC 等一手链接入口，是头条纵深补强的关键源。
WordPress 标准 feed（含 <category>），单次约 15 条，无需翻页。

需走代理：
    export HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897

用法:
    uv run python scripts/fetch_bleepingcomputer.py --days 10
    uv run python scripts/fetch_bleepingcomputer.py --start 2026-07-19 --end 2026-07-29
"""

import argparse

import lib

FEED = "https://www.bleepingcomputer.com/feed/"
SOURCE = "bc"


def _section_guess(e):
    """按 title/summary/categories 英文关键词粗判板块。BC 的 category 较全，加重依赖。"""
    cats = " ".join(e.get("categories") or []).lower()
    text = (str(e.get("title", "")) + " " + str(e.get("summary", "")) + " " + cats).lower()
    rules = [
        ("赛事活动", ["ctf", "capture the flag", "hackathon"]),
        ("漏洞情报", ["cve-", "vulnerability", "0-day", "zero-day", "rce",
                    "patch", "flaw", "exploit", "backdoor", "malware"]),
        ("政策法规", ["law", "regulation", "fine", "fined", "gdpr", "compliance",
                    "ban", "sentenced", "indicted"]),
        ("前沿技术", [" ai ", "ai-", "llm", "machine learning", "deepfake",
                    "ransomware-as-a-service"]),
    ]
    for section, kws in rules:
        if any(k in text for k in kws):
            return section
    if any(k in text for k in ["breach", "leak", "ransomware", "apt ", "attack",
                               "phishing", "hacked", "compromise"]):
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
