#!/usr/bin/env python3
"""
search-web-news — Search news via Google News RSS and Reddit.

Usage:
    python search-web-news.py <keyword> [sources] [limit] [lang] [days_back]

Examples:
    python search-web-news.py "AI agent security" google_news,reddit 15 en 90
"""

import json
import re
import ssl
import sys

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass


def _fetch(url, timeout=15):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    }
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def _strip_tags(text):
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', '', text)).strip()


def search_google_news(keyword, limit=15, lang="en"):
    results = []
    encoded = urllib.parse.quote(keyword)
    url = f"https://news.google.com/rss/search?q={encoded}&hl={lang}&gl=US&ceid=US:{lang}"
    try:
        xml_data = _fetch(url)
        root = ET.fromstring(xml_data)
        for item in root.iter("item"):
            if len(results) >= limit:
                break
            title = item.findtext("title", "")
            link = item.findtext("link", "")
            pub_date = item.findtext("pubDate", "")
            source = item.findtext("source", "")
            results.append({
                "title": title,
                "url": link,
                "source": source,
                "published": pub_date,
                "via": "google_news",
            })
    except Exception as e:
        results.append({"error": f"google_news failed: {e}", "via": "google_news"})
    return results


def search_reddit(keyword, limit=15, days_back=90):
    results = []
    encoded = urllib.parse.quote(keyword)
    url = f"https://www.reddit.com/search.json?q={encoded}&sort=new&limit={min(limit, 25)}&t=year"
    try:
        data = json.loads(_fetch(url))
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
        for child in data.get("data", {}).get("children", []):
            if len(results) >= limit:
                break
            d = child.get("data", {})
            created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
            if created < cutoff:
                continue
            results.append({
                "title": d.get("title", ""),
                "url": f"https://reddit.com{d.get('permalink', '')}",
                "source": f"r/{d.get('subreddit', '')}",
                "published": created.isoformat(),
                "score": d.get("score", 0),
                "via": "reddit",
            })
    except Exception as e:
        results.append({"error": f"reddit failed: {e}", "via": "reddit"})
    return results


def search_all(keyword, sources=None, limit=15, lang="en", days_back=90):
    if sources is None:
        sources = ["google_news", "reddit"]
    all_results = []
    for src in sources:
        if src == "google_news":
            all_results.extend(search_google_news(keyword, limit, lang))
        elif src == "reddit":
            all_results.extend(search_reddit(keyword, limit, days_back))
        time.sleep(0.5)
    return all_results


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: python search-web-news.py <keyword> [sources] [limit] [lang] [days_back]", file=sys.stderr)
        sys.exit(1)

    kw = sys.argv[1]
    sources = sys.argv[2].split(",") if len(sys.argv) > 2 and sys.argv[2] else ["google_news", "reddit"]
    limit = int(sys.argv[3]) if len(sys.argv) > 3 else 15
    lang = sys.argv[4] if len(sys.argv) > 4 else "en"
    days = int(sys.argv[5]) if len(sys.argv) > 5 else 90

    try:
        results = search_all(kw, sources, limit, lang, days)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(results, ensure_ascii=False, indent=2))
