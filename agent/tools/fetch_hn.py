#!/usr/bin/env python3
"""
fetch_hn — Fetch top stories from Hacker News matching a keyword.

Usage:
    python fetch_hn.py <keyword> [limit]
"""

import json
import sys
import urllib.request
from typing import Any


def fetch_hn(keyword: str, limit: int = 10) -> list[dict[str, Any]]:
    keyword_lower = keyword.lower()
    # Fetch top stories IDs
    with urllib.request.urlopen(
        "https://hacker-news.firebaseio.com/v0/topstories.json", timeout=10
    ) as r:
        ids = json.loads(r.read())

    results = []
    seen = 0
    for story_id in ids:
        if seen >= limit * 3:  # fetch extra to filter
            break
        try:
            with urllib.request.urlopen(
                f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json", timeout=10
            ) as r:
                story = json.loads(r.read())
            if story and story.get("type") == "story" and story.get("title"):
                title = story["title"]
                if keyword_lower in title.lower():
                    results.append(
                        {
                            "id": story_id,
                            "title": title,
                            "url": story.get("url", f"https://news.ycombinator.com/item?id={story_id}"),
                            "score": story.get("score", 0),
                            "by": story.get("by", ""),
                            "time": story.get("time", 0),
                        }
                    )
                    seen += 1
                if len(results) >= limit:
                    break
        except Exception:
            continue

    return results


if __name__ == "__main__":
    keyword = sys.argv[1] if len(sys.argv) > 1 else ""
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    if not keyword:
        print("Usage: python fetch_hn.py <keyword> [limit]", file=sys.stderr)
        sys.exit(1)

    results = fetch_hn(keyword, limit)
    print(json.dumps(results, indent=2, ensure_ascii=False))