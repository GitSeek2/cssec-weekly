"""Schneier on Security (schneier.com) RSS 抓取。境外英文观点/趋势源。

Bruce Schneier 个人博客，偏政策、趋势、密码学、隐私分析（观点性强），
适合「前沿技术 / 政策法规」做判断锚点，不作事件主力。单次约 10 条，无需翻页。

需走代理：
    export HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897

用法:
    uv run python scripts/fetch_schneier.py --days 10
    uv run python scripts/fetch_schneier.py --start 2026-07-19 --end 2026-07-29
"""

import argparse

import lib

FEED = "https://www.schneier.com/feed/"
SOURCE = "schneier"


def _section_guess(e):
    """Schneier 偏观点/趋势/密码学/隐私，默认偏向前沿技术。"""
    text = (str(e.get("title", "")) + " " + str(e.get("summary", "")) + " "
            + " ".join(e.get("categories") or [])).lower()
    rules = [
        ("漏洞情报", ["cve-", "vulnerability", "0-day", "zero-day", "flaw",
                    "exploit", "patch"]),
        ("政策法规", ["law", "regulation", "privacy", "surveillance", "policy",
                    "court", "ban", "gdpr"]),
        ("态势感知", ["breach", "attack", "ransomware", "malware", "hacked"]),
    ]
    for section, kws in rules:
        if any(k in text for k in kws):
            return section
    # Schneier 多为趋势/密码学/AI 观点分析，兜底前沿技术
    return "前沿技术"


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
