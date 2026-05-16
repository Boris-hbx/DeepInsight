#!/usr/bin/env python3
"""
search-web — Web search via Mojeek (primary) with DuckDuckGo fallback.

Usage:
    python search-web.py <keyword> [max_results] [region] [time_range]

Examples:
    python search-web.py "agentic AI security" 10 wt-wt y
"""

import html as html_mod
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def _fetch(url, headers=None, data=None, retries=3):
    hdrs = {
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.5",
    }
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, data=data, headers=hdrs)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                charset = resp.headers.get_content_charset() or "utf-8"
                return resp.read().decode(charset, errors="replace")
        except Exception:
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise


def _strip_tags(text):
    text = html_mod.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


# ── Mojeek backend ──────────────────────────────────────────────────────────

def _search_mojeek(keyword, max_results=15, time_range=""):
    results = []
    seen = set()

    for page_num in range(3):
        if len(results) >= max_results:
            break
        params = {"q": keyword, "s": str(page_num * 10)}
        if time_range:
            tr_map = {"d": "day", "w": "week", "m": "month", "y": "year"}
            params["since"] = tr_map.get(time_range, time_range)
        url = "https://www.mojeek.com/search?" + urllib.parse.urlencode(params)

        try:
            page_html = _fetch(url)
        except Exception:
            if page_num == 0:
                raise
            break

        ul_match = re.search(
            r'<ul[^>]*class="results-standard"[^>]*>(.*?)</ul>',
            page_html, re.DOTALL,
        )
        if not ul_match:
            break

        items = re.findall(r"<li[^>]*>(.*?)</li>", ul_match.group(1), re.DOTALL)
        if not items:
            break

        for item in items:
            title_m = re.search(
                r'<h2[^>]*class="title"[^>]*>.*?<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>',
                item, re.DOTALL,
            )
            if not title_m:
                title_m = re.search(
                    r'<a[^>]*href="(https?://[^"]+)"[^>]*>(.*?)</a>',
                    item, re.DOTALL,
                )
            if not title_m:
                continue

            raw_url = title_m.group(1)
            if raw_url in seen or not raw_url.startswith("http"):
                continue
            seen.add(raw_url)

            title = _strip_tags(title_m.group(2))
            if title.startswith("http"):
                title = title.rsplit("/", 1)[-1].replace("-", " ").replace("_", " ")

            snip_m = re.search(r'<p[^>]*class="s"[^>]*>(.*?)</p>', item, re.DOTALL)
            snippet = _strip_tags(snip_m.group(1))[:300] if snip_m else ""

            results.append({"title": title, "url": raw_url, "snippet": snippet})
            if len(results) >= max_results:
                break

        if page_num < 2 and len(results) < max_results:
            time.sleep(1.0)

    return results


# ── DuckDuckGo backend (fallback) ───────────────────────────────────────────

def _clean_ddg_url(raw):
    raw = html_mod.unescape(raw).strip()
    m = re.search(r"[?&]uddg=([^&]+)", raw)
    if m:
        return urllib.parse.unquote(m.group(1))
    return raw if raw.startswith("http") else ""


def _search_ddg(keyword, max_results=15, time_range=""):
    results = []
    seen = set()

    for page_num in range(3):
        if len(results) >= max_results:
            break
        params = {"q": keyword, "s": str(page_num * 30)}
        if time_range:
            params["df"] = time_range
        data = urllib.parse.urlencode(params).encode("utf-8")
        url = "https://html.duckduckgo.com/html/"

        try:
            page_html = _fetch(url, data=data)
        except Exception:
            if page_num == 0:
                raise
            break

        if "anomaly" in page_html:
            break

        links = re.findall(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
            page_html, re.DOTALL,
        )
        snippets = re.findall(
            r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
            page_html, re.DOTALL,
        )
        if not links:
            break

        for i, (raw_url, raw_title) in enumerate(links):
            u = _clean_ddg_url(raw_url)
            if not u or u in seen:
                continue
            seen.add(u)
            results.append({
                "title": _strip_tags(raw_title),
                "url": u,
                "snippet": _strip_tags(snippets[i]) if i < len(snippets) else "",
            })
            if len(results) >= max_results:
                break

        if page_num < 2 and len(results) < max_results:
            time.sleep(1.0)

    return results


# ── Public API ───────────────────────────────────────────────────────────────

def search(keyword, max_results=15, region="wt-wt", time_range=""):
    try:
        results = _search_mojeek(keyword, max_results, time_range)
        if results:
            return results
    except Exception:
        pass

    return _search_ddg(keyword, max_results, time_range)


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print(
            "Usage: python search-web.py <keyword> [max_results] [region] [time_range]",
            file=sys.stderr,
        )
        sys.exit(1)

    kw = sys.argv[1]
    max_r = int(sys.argv[2]) if len(sys.argv) > 2 else 15
    region = sys.argv[3] if len(sys.argv) > 3 else "wt-wt"
    tr = sys.argv[4] if len(sys.argv) > 4 else ""

    try:
        results = search(kw, max_r, region, tr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(
        {"query": kw, "total": len(results), "results": results},
        ensure_ascii=False, indent=2,
    ))
