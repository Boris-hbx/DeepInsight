"""fetch_hn — Fetch HN stories matching keywords."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..pipeline.step import Step, StepRegistry
from ..pipeline.context import PipelineContext

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from fetch_hn import fetch_hn


@StepRegistry.register
class FetchHNStep(Step):
    name = "fetch_hn"

    def run(self, ctx: PipelineContext) -> None:
        keywords = self.config.get("keywords", ["agent"])
        limit = self.config.get("limit", 30)
        per_keyword = max(1, limit // len(keywords))

        all_items: list[dict[str, Any]] = []
        seen_ids: set[int] = set()

        for kw in keywords:
            try:
                items = fetch_hn(kw, limit=per_keyword)
                for item in items:
                    if item["id"] not in seen_ids:
                        seen_ids.add(item["id"])
                        item["source_name"] = "Hacker News"
                        item["source_category"] = "Community"
                        all_items.append(item)
            except Exception as e:
                print(f"    [fetch_hn] keyword '{kw}': failed ({e})")

        output_name = self.outputs[0] if self.outputs else "hn_items"
        ctx.put(output_name, all_items)
        print(f"    -> {len(all_items)} HN items ({len(keywords)} keywords)")
