"""filter_date — Keep only items within a date range."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from ..pipeline.step import Step, StepRegistry
from ..pipeline.context import PipelineContext


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    s = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%a, %d %b %Y %H:%M:%S %z"):
        try:
            return datetime.strptime(s[:19], fmt[:min(len(fmt), 19)]).date()
        except ValueError:
            continue
    # Try Unix timestamp
    try:
        ts = int(s)
        if ts > 1e9:
            return datetime.fromtimestamp(ts).date()
    except (ValueError, OSError):
        pass
    return None


@StepRegistry.register
class FilterDateStep(Step):
    name = "filter_date"

    def run(self, ctx: PipelineContext) -> None:
        items = ctx.get(self.inputs[0]) if self.inputs else []
        range_days = self.config.get("range_days", 1)
        target = date.today()
        cutoff = target - timedelta(days=range_days)

        date_fields = ["pub_date", "published", "time", "date", "publishedAt", "created_at"]

        filtered = []
        for item in items:
            item_date = None
            for field in date_fields:
                if field in item:
                    item_date = _parse_date(item[field])
                    if item_date:
                        break

            if item_date is None:
                filtered.append(item)  # Keep items without dates
            elif item_date >= cutoff:
                filtered.append(item)

        output_name = self.outputs[0] if self.outputs else "filtered_items"
        ctx.put(output_name, filtered)
        print(f"    -> date filter: {len(items)} → {len(filtered)} (last {range_days}d)")
