"""search — Multi-engine search (web, arxiv, news)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from ..pipeline.step import Step, StepRegistry
from ..pipeline.context import PipelineContext

TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"


def _run_tool(script: str, args: list[str]) -> list[dict[str, Any]]:
    cmd = [sys.executable, str(TOOLS_DIR / script)] + args
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        return []
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return []


@StepRegistry.register
class SearchStep(Step):
    name = "search"

    def run(self, ctx: PipelineContext) -> None:
        engines = self.config.get("engines", ["web"])
        limit_per_engine = self.config.get("limit_per_engine", 15)

        keyword = ""
        if self.inputs:
            keyword = ctx.get(self.inputs[0])
        if not keyword:
            keyword = ctx.metadata.get("keyword", "")

        all_results: list[dict[str, Any]] = []

        for engine in engines:
            try:
                items = self._search_engine(engine, keyword, limit_per_engine)
                for item in items:
                    item["source_engine"] = engine
                all_results.extend(items)
            except Exception as e:
                print(f"    [search] {engine}: failed ({e})")

        output_name = self.outputs[0] if self.outputs else "search_results"
        ctx.put(output_name, all_results)
        print(f"    -> {len(all_results)} results from {len(engines)} engines")

    def _search_engine(self, engine: str, keyword: str, limit: int) -> list[dict[str, Any]]:
        if engine == "web":
            return _run_tool("search-web.py", [keyword, str(limit)])
        elif engine == "arxiv":
            return _run_tool("search-arxiv.py", [keyword, str(limit)])
        elif engine == "news":
            return _run_tool("search-web-news.py", [keyword])
        return []
