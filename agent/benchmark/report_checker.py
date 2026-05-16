#!/usr/bin/env python3
"""
report_checker.py — Validate report structure and URL health.

Can be used as a library (from benchmark.report_checker import ...) or CLI:
    python -m agent.benchmark.report_checker path/to/report.md
"""

import re
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


def check_structure(text: str) -> dict[str, Any]:
    """Check if a report follows the expected schema."""
    checks = {
        "has_title": bool(re.search(r"^# .+", text, re.M)),
        "has_blockquote_summary": bool(re.search(r"^> .+", text, re.M)),
        "has_top_stories": "## 最关注的事" in text or "## " in text,
        "has_sources": bool(re.search(r"\[.+?\]\(https?://.+?\)", text)),
        "has_observation": "观察小结" in text or "小结" in text,
    }
    checks["all_ok"] = all(checks.values())
    return checks


def extract_urls(text: str) -> list[str]:
    """Extract all URLs from markdown links."""
    return re.findall(r"\(https?://[^)]+\)", text)


def check_urls(text: str, timeout: int = 10) -> dict[str, Any]:
    """HEAD-check all URLs in the report."""
    raw_urls = extract_urls(text)
    urls = [u.strip("()") for u in raw_urls]
    if not urls:
        return {"total": 0, "valid": 0, "invalid": 0, "rate": 1.0, "failures": []}

    valid = 0
    failures = []
    for url in urls:
        try:
            req = urllib.request.Request(url, method="HEAD")
            req.add_header("User-Agent", "DeepDive-Agent-Checker/1.0")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status < 400:
                    valid += 1
                else:
                    failures.append({"url": url, "status": resp.status})
        except (urllib.error.URLError, urllib.error.HTTPError, OSError) as e:
            failures.append({"url": url, "error": str(e)[:100]})

    total = len(urls)
    return {
        "total": total,
        "valid": valid,
        "invalid": total - valid,
        "rate": round(valid / total, 3) if total else 1.0,
        "failures": failures[:10],
    }


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: python -m agent.benchmark.report_checker <report.md>", file=sys.stderr)
        sys.exit(1)

    path = Path(sys.argv[1])
    text = path.read_text(encoding="utf-8")

    print(f"=== Report: {path.name} ===\n")

    struct = check_structure(text)
    print("Structure checks:")
    for k, v in struct.items():
        if k == "all_ok":
            continue
        status = "OK" if v else "MISSING"
        print(f"  {k}: {status}")
    print(f"  => {'PASS' if struct['all_ok'] else 'FAIL'}\n")

    if "--check-urls" in sys.argv:
        print("URL checks (this may take a moment)...")
        url_result = check_urls(text)
        print(f"  Total: {url_result['total']}, Valid: {url_result['valid']}, Rate: {url_result['rate']}")
        for f in url_result["failures"]:
            print(f"  FAIL: {f}")


if __name__ == "__main__":
    main()
