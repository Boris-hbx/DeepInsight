"""fetch_sources — Batch-fetch RSS feeds from sources.yaml."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from ..pipeline.step import Step, StepRegistry
from ..pipeline.context import PipelineContext

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from fetch_rss import fetch_rss


@StepRegistry.register
class FetchSourcesStep(Step):
    name = "fetch_sources"

    def run(self, ctx: PipelineContext) -> None:
        sources_file = self.config.get("sources_file", "data/sources.yaml")
        limit_per_source = self.config.get("limit_per_source", 20)

        sources_path = ctx.project_root / sources_file
        sources = _load_sources(sources_path)

        all_items: list[dict[str, Any]] = []
        for src in sources:
            url = src.get("url", "")
            name = src.get("name", "")
            if not url:
                continue
            try:
                items = fetch_rss(url, limit=limit_per_source)
                for item in items:
                    item["source_name"] = name
                    item["source_category"] = src.get("category", "")
                all_items.extend(items)
            except Exception as e:
                print(f"    [fetch_sources] {name}: failed ({e})")

        output_name = self.outputs[0] if self.outputs else "raw_items"
        ctx.put(output_name, all_items)
        print(f"    -> {len(all_items)} items from {len(sources)} sources")


def _load_sources(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml
        return yaml.safe_load(text) or []
    except ImportError:
        pass
    # Minimal parser for the simple list format
    sources = []
    current: dict[str, str] = {}
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or not stripped:
            continue
        if stripped.startswith("- name:"):
            if current:
                sources.append(current)
            current = {"name": stripped.split(":", 1)[1].strip()}
        elif ":" in stripped and current:
            k, v = stripped.split(":", 1)
            current[k.strip()] = v.strip()
    if current:
        sources.append(current)
    return sources
