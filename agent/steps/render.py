"""render — Output report to file (Markdown / HTML)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from ..pipeline.step import Step, StepRegistry
from ..pipeline.context import PipelineContext


@StepRegistry.register
class RenderStep(Step):
    name = "render"

    def run(self, ctx: PipelineContext) -> None:
        report = ctx.get(self.inputs[0]) if self.inputs else ""
        fmt = self.config.get("format", "markdown")
        output_dir = self.config.get("output_dir", "data/reports")

        out_path = ctx.project_root / output_dir
        out_path.mkdir(parents=True, exist_ok=True)

        today = date.today().isoformat()
        workflow = ctx.metadata.get("workflow", "report")

        if fmt == "markdown":
            filename = f"{today}-{workflow}.md"
            (out_path / filename).write_text(report, encoding="utf-8")
        elif fmt == "html":
            filename = f"{today}-{workflow}.html"
            html = _md_to_html(report)
            (out_path / filename).write_text(html, encoding="utf-8")
        else:
            filename = f"{today}-{workflow}.md"
            (out_path / filename).write_text(report, encoding="utf-8")

        full_path = out_path / filename
        output_name = self.outputs[0] if self.outputs else "output_path"
        ctx.put(output_name, str(full_path))
        print(f"    -> saved: {full_path}")


def _md_to_html(md: str) -> str:
    """Minimal markdown to HTML (headings + paragraphs)."""
    lines = md.splitlines()
    html_lines = ["<!DOCTYPE html><html><head><meta charset='utf-8'></head><body>"]
    for line in lines:
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("### "):
            html_lines.append(f"<h3>{line[4:]}</h3>")
        elif line.startswith("- "):
            html_lines.append(f"<li>{line[2:]}</li>")
        elif line.strip():
            html_lines.append(f"<p>{line}</p>")
    html_lines.append("</body></html>")
    return "\n".join(html_lines)
