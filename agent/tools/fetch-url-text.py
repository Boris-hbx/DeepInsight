#!/usr/bin/env python3
"""
fetch-url-text — Fetch a URL and return its plain text content.

Usage:
    python fetch-url-text.py <url> [max_chars] [timeout]

Examples:
    python fetch-url-text.py "https://example.com/article" 5000 15
"""

import json
import re
import ssl
import sys
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


def _strip_html(html):
    html = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<nav[^>]*>.*?</nav>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<footer[^>]*>.*?</footer>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<header[^>]*>.*?</header>", "", html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r"<!--.*?-->", "", html, flags=re.DOTALL)
    html = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</?p[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</?div[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</?h[1-6][^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"</?li[^>]*>", "\n", html, flags=re.IGNORECASE)
    html = re.sub(r"<[^>]+>", "", html)
    import html as html_mod
    html = html_mod.unescape(html)
    lines = [line.strip() for line in html.splitlines()]
    lines = [l for l in lines if l]
    return "\n".join(lines)


def _extract_title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
    if m:
        import html as html_mod
        return html_mod.unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip()
    return ""


def fetch_url_text(url, max_chars=5000, timeout=15):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        raw = resp.read().decode(charset, errors="replace")

    title = _extract_title(raw)
    text = _strip_html(raw)
    if len(text) > max_chars:
        text = text[:max_chars] + "..."

    return {"url": url, "title": title, "length": len(text), "text": text}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fetch-url-text.py <url> [max_chars] [timeout]", file=sys.stderr)
        sys.exit(1)

    url = sys.argv[1]
    max_chars = int(sys.argv[2]) if len(sys.argv) > 2 else 5000
    timeout = int(sys.argv[3]) if len(sys.argv) > 3 else 15

    try:
        result = fetch_url_text(url, max_chars, timeout)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(result, ensure_ascii=False, indent=2))
