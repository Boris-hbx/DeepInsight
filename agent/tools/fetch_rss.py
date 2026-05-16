#!/usr/bin/env python3
"""
fetch_rss — Fetch and parse items from an RSS or Atom feed.

Usage:
    python fetch_rss.py <url> [limit]
"""

import sys
import urllib.request
import xml.etree.ElementTree as ET

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
)


def fetch_rss(url: str, limit: int = 10) -> list[dict]:
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=15) as r:
        raw = r.read()

    root = ET.fromstring(raw)

    # Try RSS 2.0
    channel = root.find("channel")
    if channel is not None:
        return _parse_rss(channel, limit)

    # Try Atom (namespace or bare)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns) or root.findall("entry")
    if entries:
        return _parse_atom(entries, limit)

    # Try RSS 1.0 (RDF)
    rdf_ns = {"rdf": "http://purl.org/rss/1.0/"}
    rdf_items = root.findall("rdf:item", rdf_ns)
    if rdf_items:
        return _parse_rdf(rdf_items, limit)

    return []


def _parse_rss(channel, limit: int) -> list[dict]:
    items = []
    for item in channel.findall("item"):
        if len(items) >= limit:
            break
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        desc = (item.findtext("description") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()
        if title:
            items.append({
                "title": title,
                "link": link,
                "description": desc[:200] + ("..." if len(desc) > 200 else ""),
                "pub_date": pub_date,
            })
    return items


def _parse_atom(entries, limit: int) -> list[dict]:
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    items = []
    for entry in entries:
        if len(items) >= limit:
            break
        title = (entry.findtext("atom:title", namespaces=ns) or entry.findtext("title") or "").strip()
        link_el = entry.find("atom:link", ns) or entry.find("link")
        link = (link_el.get("href", "") if link_el is not None else "").strip()
        summary = (entry.findtext("atom:summary", namespaces=ns) or entry.findtext("summary") or "").strip()
        updated = (entry.findtext("atom:updated", namespaces=ns) or entry.findtext("updated") or "").strip()
        if title:
            items.append({
                "title": title,
                "link": link,
                "description": summary[:200] + ("..." if len(summary) > 200 else ""),
                "pub_date": updated,
            })
    return items


def _parse_rdf(rdf_items, limit: int) -> list[dict]:
    items = []
    for item in rdf_items:
        if len(items) >= limit:
            break
        title = (item.findtext("{http://purl.org/rss/1.0/}title") or "").strip()
        link = (item.findtext("{http://purl.org/rss/1.0/}link") or "").strip()
        desc = (item.findtext("{http://purl.org/rss/1.0/}description") or "").strip()
        if title:
            items.append({
                "title": title,
                "link": link,
                "description": desc[:200] + ("..." if len(desc) > 200 else ""),
                "pub_date": "",
            })
    return items


if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else ""
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    if not url:
        print("Usage: python fetch_rss.py <url> [limit]", file=sys.stderr)
        sys.exit(1)

    items = fetch_rss(url, limit)
    import json
    print(json.dumps(items, indent=2, ensure_ascii=False))
