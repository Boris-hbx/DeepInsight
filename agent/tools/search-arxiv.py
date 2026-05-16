#!/usr/bin/env python3
"""
search-arxiv — Search arXiv papers via the public API.

Usage:
    python search-arxiv.py <keyword> [max_results] [sort_by] [sort_order] [categories]

Examples:
    python search-arxiv.py "self-evolving agent" 10 submittedDate descending cs.AI,cs.CL
"""

import json
import ssl
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

ARXIV_API = "http://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"


def search_arxiv(keyword, max_results=10, sort_by="submittedDate",
                 sort_order="descending", categories=None):
    query = keyword
    if categories:
        cat_q = " OR ".join(f"cat:{c}" for c in categories)
        query = f"({query}) AND ({cat_q})"

    params = {
        "search_query": query,
        "start": 0,
        "max_results": max_results,
        "sortBy": sort_by,
        "sortOrder": sort_order,
    }
    url = f"{ARXIV_API}?{urllib.parse.urlencode(params)}"

    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "search-arxiv/1.0"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = resp.read().decode("utf-8")
            break
        except Exception:
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
                continue
            raise

    root = ET.fromstring(data)
    papers = []
    for entry in root.findall(f"{ATOM}entry"):
        entry_id = entry.findtext(f"{ATOM}id", "")
        if "arxiv.org/abs/" not in entry_id:
            continue

        arxiv_id = entry_id.split("/abs/")[-1]
        title = " ".join(entry.findtext(f"{ATOM}title", "").split())
        summary = " ".join(entry.findtext(f"{ATOM}summary", "").split())
        authors = [a.findtext(f"{ATOM}name", "") for a in entry.findall(f"{ATOM}author")]
        published = entry.findtext(f"{ATOM}published", "")

        pdf_url = f"https://arxiv.org/pdf/{arxiv_id}"
        for link in entry.findall(f"{ATOM}link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href", pdf_url)
                break

        cats = []
        for c in entry.findall(f"{ARXIV_NS}primary_category"):
            if c.get("term"):
                cats.append(c.get("term"))

        papers.append({
            "arxiv_id": arxiv_id,
            "title": title,
            "authors": authors,
            "summary": summary[:500],
            "published": published,
            "pdf_url": pdf_url,
            "categories": cats,
        })

    return papers


if __name__ == "__main__":
    if len(sys.argv) < 2 or not sys.argv[1].strip():
        print("Usage: python search-arxiv.py <keyword> [max_results] [sort_by] [sort_order] [categories]", file=sys.stderr)
        sys.exit(1)

    kw = sys.argv[1]
    max_r = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    sort_by = sys.argv[3] if len(sys.argv) > 3 else "submittedDate"
    sort_order = sys.argv[4] if len(sys.argv) > 4 else "descending"
    cats = sys.argv[5].split(",") if len(sys.argv) > 5 and sys.argv[5] else []

    try:
        results = search_arxiv(kw, max_r, sort_by, sort_order, cats)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps(results, ensure_ascii=False, indent=2))
