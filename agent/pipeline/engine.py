"""PipelineEngine — loads workflow YAML and executes steps in sequence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .context import PipelineContext
from .step import Step, StepRegistry
from .gate import PolicyGate, GateResult, PolicyDenied

try:
    import yaml as _yaml
except ImportError:
    _yaml = None


def _load_yaml(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if _yaml:
        return _yaml.safe_load(text)
    import json
    if text.strip().startswith("{"):
        return json.loads(text)
    return _parse_yaml_minimal(text)


def _parse_yaml_minimal(text: str) -> dict[str, Any]:
    """Minimal YAML parser for workflow files when pyyaml is unavailable."""
    import re
    result: dict[str, Any] = {}
    current_key = ""
    current_list: list[Any] = []
    current_item: dict[str, Any] = {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        if indent == 0 and ":" in stripped:
            if current_key and current_list:
                if current_item:
                    current_list.append(current_item)
                    current_item = {}
                result[current_key] = current_list
                current_list = []
            k, v = stripped.split(":", 1)
            k, v = k.strip(), v.strip()
            if not v:
                current_key = k
                current_list = []
            else:
                result[k] = v
                current_key = ""

        elif stripped.startswith("- step:"):
            if current_item:
                current_list.append(current_item)
            current_item = {"step": stripped.split(":", 1)[1].strip()}

        elif indent >= 4 and current_item and ":" in stripped:
            k, v = stripped.split(":", 1)
            k, v = k.strip(), v.strip()
            if v.startswith("[") and v.endswith("]"):
                items = [x.strip().strip("'\"") for x in v[1:-1].split(",")]
                current_item[k] = items
            elif v.isdigit():
                current_item[k] = int(v)
            elif v in ("true", "false"):
                current_item[k] = v == "true"
            else:
                current_item[k] = v

    if current_key:
        if current_item:
            current_list.append(current_item)
        result[current_key] = current_list

    return result


class PipelineEngine:
    def __init__(self, gate: PolicyGate | None = None, verbose: bool = False) -> None:
        self.gate = gate or PolicyGate()
        self.verbose = verbose

    def run(self, workflow_path: Path, task: str, dry_run: bool = False, **kwargs: Any) -> PipelineContext:
        workflow = _load_yaml(workflow_path)
        ctx = PipelineContext(task=task, **kwargs)
        ctx.metadata["workflow"] = workflow.get("name", workflow_path.stem)

        steps_def = workflow.get("steps", [])
        print(f"\n[Pipeline] {workflow.get('name', '?')} — {len(steps_def)} steps")

        for i, step_def in enumerate(steps_def):
            step_name = step_def.get("step", "?")
            config = step_def.get("config", {})
            inputs = step_def.get("inputs", [])
            outputs = step_def.get("outputs", [])
            skip_if = step_def.get("skip_if", "")
            inputs_from_task = step_def.get("inputs_from_task", [])

            # Inject task params into context
            for param in inputs_from_task:
                if param in kwargs:
                    ctx.put(param, kwargs[param])

            if dry_run:
                print(f"  [{i+1}] {step_name} (inputs={inputs}, outputs={outputs})")
                continue

            # Gate check
            gate_result = self.gate.check(step_name, ctx)
            if gate_result == GateResult.DENY:
                raise PolicyDenied(step_name)
            if gate_result == GateResult.REQUIRE_APPROVAL:
                print(f"  [{i+1}] {step_name} — REQUIRES APPROVAL (skipping)")
                ctx.add_log(step_name, "skipped", "requires approval")
                continue

            # Resolve step class
            step_cls = StepRegistry.get(step_name)
            step = step_cls(config=config)
            step.inputs = inputs
            step.outputs = outputs

            # Skip condition
            if skip_if:
                try:
                    if eval(skip_if, {"ctx": ctx}):
                        print(f"  [{i+1}] {step_name} — skipped")
                        ctx.add_log(step_name, "skipped", skip_if)
                        continue
                except Exception:
                    pass

            if step.skip_condition(ctx):
                print(f"  [{i+1}] {step_name} — skipped (condition)")
                ctx.add_log(step_name, "skipped", "skip_condition")
                continue

            # Execute
            print(f"  [{i+1}] {step_name}...")
            try:
                step.run(ctx)
                ctx.add_log(step_name, "ok")
                if self.verbose:
                    for out in outputs:
                        if ctx.has(out):
                            val = ctx.get(out)
                            size = len(val) if isinstance(val, (list, str)) else "?"
                            print(f"       -> {out}: {size} items/chars")
            except Exception as e:
                ctx.add_log(step_name, "error", str(e))
                print(f"  [{i+1}] {step_name} — ERROR: {e}")
                raise

        if dry_run:
            print("[Pipeline] dry-run complete")
        else:
            print(f"[Pipeline] done in {ctx.elapsed():.1f}s")

        return ctx
