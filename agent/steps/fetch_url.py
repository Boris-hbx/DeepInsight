"""fetch_url — Fetch full text from URL(s)."""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from ..pipeline.step import Step, StepRegistry
from ..pipeline.context import PipelineContext

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))


@StepRegistry.register
class FetchURLStep(Step):
    name = "fetch_url"

    def run(self, ctx: PipelineContext) -> None:
        from importlib import import_module
        spec = import_module("fetch-url-text")
        fetch_url_text = spec.fetch_url_text

        max_chars = self.config.get("max_chars", 5000)
        batch = self.config.get("batch", False)
        concurrency = self.config.get("concurrency", 5)

        # Single URL mode
        if not batch:
            url = ctx.get(self.inputs[0]) if self.inputs else self.config.get("url", "")
            if isinstance(url, str):
                result = fetch_url_text(url, max_chars=max_chars)
                output_name = self.outputs[0] if self.outputs else "full_text"
                ctx.put(output_name, result)
                print(f"    -> fetched {result.get('title', url)[:60]}")
                return

        # Batch mode: input is a list of items with 'url' or 'link' field
        items = ctx.get(self.inputs[0]) if self.inputs else []
        urls = []
        for item in items:
            u = item.get("url") or item.get("link", "")
            if u:
                urls.append(u)

        results: list[dict[str, Any]] = []
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {pool.submit(fetch_url_text, u, max_chars): u for u in urls[:20]}
            for future in as_completed(futures):
                try:
                    results.append(future.result())
                except Exception:
                    pass

        output_name = self.outputs[0] if self.outputs else "full_texts"
        ctx.put(output_name, results)
        print(f"    -> fetched {len(results)}/{len(urls)} URLs")
