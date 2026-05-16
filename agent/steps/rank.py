"""rank — LLM-based relevance ranking."""

from __future__ import annotations

import json
import time
from typing import Any

import anthropic

from ..pipeline.step import Step, StepRegistry
from ..pipeline.context import PipelineContext


def _get_client() -> anthropic.Anthropic:
    from ..loop import get_anthropic_client
    return get_anthropic_client()


def _call_with_retry(client: anthropic.Anthropic, **kwargs) -> Any:
    for attempt in range(5):
        try:
            return client.messages.create(**kwargs)
        except anthropic.RateLimitError:
            wait = 2 ** attempt * 5
            print(f"    [rate limited, waiting {wait}s...]")
            time.sleep(wait)
    raise RuntimeError("Rate limit exceeded after 5 retries")


@StepRegistry.register
class RankStep(Step):
    name = "rank"

    def run(self, ctx: PipelineContext) -> None:
        items = ctx.get(self.inputs[0]) if self.inputs else []
        topic = self.config.get("topic", ctx.metadata.get("task", ""))
        top_k = self.config.get("top_k", 10)

        if len(items) <= top_k:
            output_name = self.outputs[0] if self.outputs else "ranked_items"
            ctx.put(output_name, items)
            print(f"    -> {len(items)} items (no ranking needed)")
            return

        # Format items for LLM
        item_lines = []
        for i, item in enumerate(items[:50]):  # Cap at 50 for context
            title = item.get("title", "")
            desc = (item.get("description") or item.get("text", ""))[:100]
            item_lines.append(f"{i}: {title} — {desc}")

        prompt = f"""Rank these items by relevance to the topic: "{topic}"

Items:
{chr(10).join(item_lines)}

Output a JSON array of the top {top_k} item indices (0-based), ordered by relevance.
Example: [3, 0, 7, 1, ...]
Output ONLY the JSON array, nothing else."""

        client = _get_client()
        msg = _call_with_retry(
            client,
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        text = msg.content[0].text.strip()
        # Parse indices
        try:
            if text.startswith("```"):
                text = "\n".join(text.splitlines()[1:-1])
            indices = json.loads(text)
        except (json.JSONDecodeError, ValueError):
            indices = list(range(min(top_k, len(items))))

        ranked = [items[i] for i in indices if i < len(items)]

        output_name = self.outputs[0] if self.outputs else "ranked_items"
        ctx.put(output_name, ranked)
        print(f"    -> ranked top {len(ranked)} from {len(items)}")
