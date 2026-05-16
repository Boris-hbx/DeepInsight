#!/usr/bin/env python3
"""
filter-by-date — Filter a JSON array by a date/timestamp field.

Usage:
    python filter-by-date.py <json_file> <date_field> [target_date] [range_days]
    cat data.json | python filter-by-date.py - <date_field> [target_date] [range_days]

    json_file:    path to JSON file, or "-" to read from stdin
    date_field:   JSON key containing a date or unix timestamp (e.g. "time", "pub_date")
    target_date:  YYYY-MM-DD (default: today)
    range_days:   include items from this many days before target_date (default: 0 = today only)
"""

import json
import sys
from datetime import date, datetime, timedelta


def parse_date_value(val) -> date | None:
    if isinstance(val, (int, float)):
        try:
            return datetime.fromtimestamp(val).date()
        except (OSError, ValueError):
            return None
    if isinstance(val, str):
        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%fZ", "%Y-%m-%dT%H:%M:%SZ"):
            try:
                return datetime.strptime(val.strip(), fmt).date()
            except ValueError:
                continue
    return None


def main() -> None:
    if len(sys.argv) < 3:
        print("Usage: python filter-by-date.py <json_file> <date_field> [target_date] [range_days]", file=sys.stderr)
        sys.exit(1)

    json_source = sys.argv[1]
    date_field = sys.argv[2]
    target_str = sys.argv[3] if len(sys.argv) > 3 else "today"
    target = date.today() if target_str.lower() == "today" else date.fromisoformat(target_str)
    range_days = int(sys.argv[4]) if len(sys.argv) > 4 else 0

    earliest = target - timedelta(days=range_days)

    if json_source == "-":
        raw = sys.stdin.read()
    else:
        with open(json_source, encoding="utf-8") as f:
            raw = f.read()

    items = json.loads(raw)
    if not isinstance(items, list):
        print("Error: input must be a JSON array", file=sys.stderr)
        sys.exit(1)

    filtered = []
    for item in items:
        val = item.get(date_field)
        if val is None:
            continue
        d = parse_date_value(val)
        if d and earliest <= d <= target:
            filtered.append(item)

    print(json.dumps(filtered, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()