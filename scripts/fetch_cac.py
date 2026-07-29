"""中央网信办 (cac.gov.cn) 列表页抓取。

两个静态 .htm 列表页（服务端渲染）：
    网信发布: https://www.cac.gov.cn/wxzw/wxfb/A093702index_1.htm
    网络安全: https://www.cac.gov.cn/wxzw/wlaq/A093705index_1.htm

每条 HTML 形如:
    <li><h5><a href=//www.cac.gov.cn/2026-07/24/c_xxx.htm target=_blank title="标题">标题</a></h5>
        <div class="times">2026-07-24</div></li>

注意: href 协议相对(补 https:)，title 属性未加引号需用宽松正则。
翻页: index_1.htm / index_2.htm ... 当某页无窗口内条目即停。
"""

import argparse
import re

import lib

PAGES = {
    "网信发布": "https://www.cac.gov.cn/wxzw/wxfb/A093702index_{n}.htm",
    "网络安全": "https://www.cac.gov.cn/wxzw/wlaq/A093705index_{n}.htm",
}

# 一条 = <li> ... <a ... href=URL ... title="标题"> ... <div class="times">日期</div>
# 用宽松正则逐条捕获。
_LI = re.compile(r"<li\b.*?</li>", re.S | re.I)
_HREF = re.compile(r'href=([^"\s>]+)', re.I)
_TITLE = re.compile(r'title=(?:"([^"]*)"|([^\s>]+))', re.I)
_TIME = re.compile(r'class=["\']times["\'][^>]*>\s*(\d{4}-\d{1,2}-\d{1,2})', re.I)


def _parse_page(html):
    out = []
    for li in _LI.findall(html or ""):
        href = _HREF.search(li)
        title = _TITLE.search(li)
        tm = _TIME.search(li)
        if not (href and title and tm):
            continue
        h = href.group(1).strip()
        if h.startswith("//"):
            h = "https:" + h
        elif h.startswith("/"):
            h = "https://www.cac.gov.cn" + h
        t = (title.group(1) or title.group(2) or "").strip()
        d = lib.parse_date_iso(tm.group(1))
        out.append({"title": t, "url": h, "date": d})
    return out


def main():
    ap = argparse.ArgumentParser()
    lib.add_window_args(ap)
    args = ap.parse_args()

    start, end = lib.resolve_window(args)
    errors = []
    items = []
    for channel, tpl in PAGES.items():
        for n in range(1, 6):  # 每栏目最多翻 5 页
            url = tpl.format(n=n)
            try:
                html, status = lib.http_get(url)
            except lib.urllib.error.HTTPError as e:
                # 404 = 该页不存在（已到列表末尾），属正常停止，不算错误
                if e.code == 404:
                    break
                errors.append(f"cac/{channel} p{n}: HTTP {e.code}")
                break
            except Exception as e:  # noqa: BLE001
                errors.append(f"cac/{channel} p{n}: {type(e).__name__}: {e}")
                break
            entries = _parse_page(html)
            if not entries:
                break
            kept = 0
            for e in entries:
                if lib.in_range(e["date"], start, end):
                    items.append(lib.item(
                        source="cac",
                        section_guess="政策法规",
                        title=e["title"],
                        url=e["url"],
                        date=e["date"],
                        summary="",
                        extra={"channel": channel},
                    ))
                    kept += 1
            # 该页没有窗口内条目（已翻到更早）-> 停
            if kept == 0:
                break

    lib.emit(items, errors)


if __name__ == "__main__":
    lib.run_main(main)
