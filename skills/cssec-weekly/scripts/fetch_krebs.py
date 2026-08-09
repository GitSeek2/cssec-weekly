"""Krebs on Security (krebsonsecurity.com) RSS 抓取。境外英文深度调查源。

Brian Krebs 个人调查博客，独家深度报道为主（地下产业链、欺诈、APT 起底），
产量小但重磅，常可作为头条纵深的一手引用。单次约 10 条，无需翻页。

需走代理：
    export HTTPS_PROXY=http://127.0.0.1:7897 HTTP_PROXY=http://127.0.0.1:7897

用法:
    uv run python scripts/fetch_krebs.py --days 10
    uv run python scripts/fetch_krebs.py --start 2026-07-19 --end 2026-07-29
"""

import argparse

import lib

FEED = "https://krebsonsecurity.com/feed/"
SOURCE = "krebs"


def _section_guess(e):
    """Krebs 偏调查/欺诈/地下产业，默认偏向态势感知。"""
    text = (str(e.get("title", "")) + " " + str(e.get("summary", "")) + " "
            + " ".join(e.get("categories") or [])).lower()
    rules = [
        ("漏洞情报", ["cve-", "vulnerability", "0-day", "zero-day", "flaw",
                    "exploit", "patch"]),
        ("政策法规", ["indicted", "sentenced", "arrest", "law", "sanction",
                    "department of justice", "doj"]),
        ("前沿技术", [" ai ", "ai-", "llm", "machine learning"]),
    ]
    for section, kws in rules:
        if any(k in text for k in kws):
            return section
    # Krebs 多为攻击/欺诈/地下产业调查，兜底态势感知
    return "态势感知"


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
