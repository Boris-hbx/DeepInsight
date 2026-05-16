"""dedup — URL normalization + LLM semantic dedup."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

import anthropic

from ..pipeline.step import Step, StepRegistry
from ..pipeline.context import PipelineContext


def _normalize_url(url: str) -> str:
    parsed = urlparse(url)
    # Remove tracking params
    params = parse_qs(parsed.query)
    clean_params = {k: v for k, v in params.items() if not k.startswith("utm_")}
    cleaned = parsed._replace(
        query=urlencode(clean_params, doseq=True),
        fragment="",
    )
    return urlunparse(cleaned).rstrip("/")


def _url_dedup(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Remove exact URL duplicates after normalization."""
    seen: set[str] = set()
    unique = []
    for item in items:
        url = item.get("url") or item.get("link", "")
        norm = _normalize_url(url) if url else ""
        if norm and norm in seen:
            continue
        if norm:
            seen.add(norm)
        unique.append(item)
    return unique


@StepRegistry.register
class DedupStep(Step):
    name = "dedup"

    def run(self, ctx: PipelineContext) -> None:
        # Merge all input artifacts into one list
        merged = ctx.merge_lists(self.inputs) if self.inputs else []

        # Phase 1: URL normalization dedup
        after_url = _url_dedup(merged)
        removed = len(merged) - len(after_url)
        print(f"    -> URL dedup: {len(merged)} → {len(after_url)} (-{removed})")

        # Phase 2: Title fuzzy dedup (simple Jaccard on words)
        after_title = _title_dedup(after_url)
        removed2 = len(after_url) - len(after_title)
        if removed2:
            print(f"    -> Title dedup: -{removed2}")

        output_name = self.outputs[0] if self.outputs else "unique_items"
        ctx.put(output_name, after_title)


def _title_dedup(items: list[dict[str, Any]], threshold: float = 0.7) -> list[dict[str, Any]]:
    """Remove items with very similar titles (Jaccard > threshold)."""
    unique = []
    title_sets: list[set[str]] = []

    for item in items:
        title = (item.get("title") or "").lower()
        words = set(title.split())
        if not words:
            unique.append(item)
            continue

        is_dup = False
        for existing in title_sets:
            if not existing:
                continue
            jaccard = len(words & existing) / len(words | existing)
            if jaccard > threshold:
                is_dup = True
                break

        if not is_dup:
            unique.append(item)
            title_sets.append(words)

    return unique
