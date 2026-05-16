#!/usr/bin/env python3
"""
batch-fetch-summarize — Fetch multiple URLs and extract key content.

Usage:
    python batch-fetch-summarize.py <url1> [url2] [url3] ...

Options via env vars (to keep CLI simple):
    MAX_CHARS=3000  max chars per page
    TIMEOUT=15      request timeout in seconds
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
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass


def _fetch_text(url, max_chars=3000, timeout=15):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        html = resp.read().decode(charset, errors="replace")

    # Strip script/style tags
    html = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # Extract title
    title_m = re.search(r'<title[^>]*>(.*?)</title>', html, re.DOTALL | re.IGNORECASE)
    title = re.sub(r'\s+', ' ', title_m.group(1)).strip() if title_m else ""
    # Strip all tags
    text = re.sub(r'<[^>]+>', ' ', html)
    text = re.sub(r'\s+', ' ', text).strip()

    return {
        "url": url,
        "title": title,
        "text": text[:max_chars],
        "length": len(text),
    }


def batch_fetch(urls, max_chars=3000, timeout=15, concurrency=5):
    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        futures = {pool.submit(_fetch_text, u, max_chars, timeout): u for u in urls}
        for f in as_completed(futures):
            url = futures[f]
            try:
                results.append(f.result())
            except Exception as e:
                results.append({"url": url, "error": str(e)})
    return results


if __name__ == "__main__":
    import os

    if len(sys.argv) < 2:
        print("Usage: python batch-fetch-summarize.py <url1> [url2] ...", file=sys.stderr)
        sys.exit(1)

    urls = [u for u in sys.argv[1:] if u.startswith("http")]
    if not urls:
        print("Error: no valid URLs provided", file=sys.stderr)
        sys.exit(1)

    max_chars = int(os.environ.get("MAX_CHARS", "3000"))
    timeout = int(os.environ.get("TIMEOUT", "15"))

    results = batch_fetch(urls, max_chars, timeout)
    print(json.dumps(results, ensure_ascii=False, indent=2))
