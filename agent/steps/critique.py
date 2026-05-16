"""critique — Blue Agent adversarial review."""

from __future__ import annotations

from typing import Any

from ..pipeline.step import Step, StepRegistry
from ..pipeline.context import PipelineContext
from ..loop import get_anthropic_client


@StepRegistry.register
class CritiqueStep(Step):
    name = "critique"

    def run(self, ctx: PipelineContext) -> None:
        report = ctx.get(self.inputs[0]) if self.inputs else ""
        max_challenges = self.config.get("max_challenges", 3)
        task = ctx.metadata.get("task", "")

        from ..blue_agent import BlueAgent
        client = get_anthropic_client()
        blue = BlueAgent(client=client)

        challenges, usage = blue.challenge_report(report, task)
        challenges = challenges[:max_challenges]

        if challenges:
            blue_section = blue.format_report_section(challenges)
            report_with_critique = report + blue_section
        else:
            report_with_critique = report

        output_name = self.outputs[0] if self.outputs else "report_with_critique"
        ctx.put(output_name, report_with_critique)
        print(f"    -> {len(challenges)} challenges appended")

    def skip_condition(self, ctx: PipelineContext) -> bool:
        return ctx.metadata.get("skip_blue", False)
