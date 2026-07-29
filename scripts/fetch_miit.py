"""工信部 (miit.gov.cn) 列表抓取。

miit 的 index.html 是 JS 空壳（不含文章链接），底层走 JPaas unit API：
    GET https://www.miit.gov.cn/api-gateway/jpaas-publish-server/front/page/build/unit
        ?parseType=buildstatic&webId=...&tplSetId=...&pageType=column
        &tagId=右侧内容&editType=null&pageId=...

webId/tplSetId/pageId 是 per-section 且可能轮换，不能写死。
健壮做法：抓该 section 的 index.html，从 <script ... queryData='{...}'> 里抠出这三个 id，
再拼 unit API。返回 data.html 内含 <li><a title=...><span class=fr>YYYY-MM-DD</span>。

注意: 只支持 GET（POST 返回 501）。
"""

import argparse
import re
import urllib.parse

import lib

UNIT_API = "https://www.miit.gov.cn/api-gateway/jpaas-publish-server/front/page/build/unit"

SECTIONS = {
    "时政要闻": "https://www.miit.gov.cn/xwfb/szyw/index.html",
    "工信动态": "https://www.miit.gov.cn/xwfb/gxdt/index.html",
    # "部领导活动" 与 "工信动态" 共用 gxdt 页面，故不重复
    "政策文件": "https://www.miit.gov.cn/search/zcwjk.html",
    "行政规范文件": "https://www.miit.gov.cn/zc/wjxzfl/xzgfxwj/index.html",
    "文件公示": "https://www.miit.gov.cn/zwgk/wjgs/index.html",
}

_LI = re.compile(r"<li\b[^>]*>(.*?)</li>", re.S | re.I)
_A = re.compile(r"<a\b[^>]*>(.*?)</a>", re.S | re.I)
# href 值可能带引号(href="...")或不带(href=//...)，分别捕获
_HREF = re.compile(r'href=(?:"([^"]*)"|([^"\s>]+))', re.I)
_TITLE = re.compile(r'title=(?:"([^"]*)"|([^\s>]+))', re.I)
_DATE = re.compile(r"(\d{4}-\d{1,2}-\d{1,2})")


def _extract_query_ids(html):
    """从 section 的 index.html 中解析出 webId/tplSetId/pageId/tagId。

    这些 id 嵌在 unitbuild.js 的 <script> 标签里（HTML 属性 + 单引号 Python 字典混排），
    直接按 key 抓 32 位 hex 最稳。
    """
    html = html or ""
    # 只在 unitbuild 脚本块范围内抓，避免误命中页面其它片段
    m = re.search(r'<script\b[^>]*unitbuild\.js[^>]*>.*?</script>',
                  html, re.S | re.I)
    block = m.group(0) if m else html

    def grab(key):
        mm = re.search(key + r"'\s*:\s*'([0-9a-f]{32})'", block)  # 'key':'hex'
        if mm:
            return mm.group(1)
        mm = re.search(key + r'="\s*([0-9a-f]{32})', block)  # key="hex"
        return mm.group(1) if mm else ""

    web = grab("webId")
    tpl = grab("tplSetId")
    page = grab("pageId")
    if not (web and page):
        return None
    tm = re.search(r"tagId'\s*:\s*'([^']+)'", block)
    return {
        "webId": web,
        "tplSetId": tpl,
        "pageId": page,
        "tagId": tm.group(1) if tm else "右侧内容",
    }


def _fetch_section_list(section_url):
    """返回 list 页 HTML（unit API 返回的 data.html）；失败返回 ''。"""
    html, _ = lib.http_get(section_url)
    qd = _extract_query_ids(html)
    if not qd:
        return ""
    params = {
        "parseType": "buildstatic",
        "webId": qd.get("webId", ""),
        "tplSetId": qd.get("tplSetId", ""),
        "pageType": "column",
        "tagId": qd.get("tagId") or "右侧内容",
        "editType": "null",
        "pageId": qd.get("pageId", ""),
    }
    qs = "&".join(f"{k}={urllib.parse.quote(str(v))}" for k, v in params.items())
    url = f"{UNIT_API}?{qs}"
    data = lib.http_get_json(url)
    if isinstance(data, dict):
        return (data.get("data") or {}).get("html") or ""
    return ""


def _parse_list(list_html, channel):
    out = []
    for li in _LI.findall(list_html or ""):
        a = _A.search(li)
        if not a:
            continue
        atag = a.group(0)
        href = _HREF.search(atag)
        title = _TITLE.search(atag)
        # 标题也可能在 <a> 文本里
        a_text = lib.strip_tags(a.group(1))
        d = _DATE.search(li)
        h = ""
        if href:
            h = (href.group(1) or href.group(2) or "").strip()
        if h.startswith("//"):
            h = "https:" + h
        elif h.startswith("/"):
            h = "https://www.miit.gov.cn" + h
        t = ""
        if title:
            t = (title.group(1) or title.group(2) or "").strip()
        if not t:
            t = a_text
        date = lib.parse_date_iso(d.group(1)) if d else None
        if t and h:
            out.append({"title": t, "url": h, "date": date, "channel": channel})
    return out


def main():
    ap = argparse.ArgumentParser()
    lib.add_window_args(ap)
    args = ap.parse_args()

    start, end = lib.resolve_window(args)
    errors = []
    items = []
    for channel, url in SECTIONS.items():
        try:
            list_html = _fetch_section_list(url)
        except Exception as e:  # noqa: BLE001
            errors.append(f"miit/{channel}: {type(e).__name__}: {e}")
            continue
        for e in _parse_list(list_html, channel):
            if lib.in_range(e["date"], start, end):
                items.append(lib.item(
                    source="miit",
                    section_guess="政策法规",
                    title=e["title"],
                    url=e["url"],
                    date=e["date"],
                    summary="",
                    extra={"channel": channel},
                ))

    lib.emit(items, errors)


if __name__ == "__main__":
    lib.run_main(main)
