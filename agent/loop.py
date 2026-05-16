#!/usr/bin/env python3
"""
AgentLoop — the main self-evolving agent loop.
"""

import json as _json
import os
import sys
import tempfile
from datetime import date
from pathlib import Path
from typing import Any

import anthropic


def _extract_text(msg) -> str:
    """Extract text from an Anthropic message, skipping ThinkingBlocks."""
    for block in msg.content:
        if hasattr(block, "text"):
            return block.text
    return ""

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

ROOT = Path(__file__).resolve().parent  # agent/
TEMP_DIR = ROOT / "tools" / ".tmp"
WORKFLOWS_DIR = ROOT / "workflows"

# Ensure stdout supports UTF-8 (Windows console fix)
if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load from Claude Code settings.json (~/.claude/settings.json) if available
_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


def _load_api_key() -> str:
    if os.environ.get("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    if _SETTINGS_PATH.exists():
        try:
            settings = _json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
            env_cfg = settings.get("env", {})
            if env_cfg.get("ANTHROPIC_AUTH_TOKEN"):
                return env_cfg["ANTHROPIC_AUTH_TOKEN"]
        except Exception:
            pass
    raise ValueError("No API key found: set ANTHROPIC_API_KEY env var or check ~/.claude/settings.json")


def _load_base_url() -> str | None:
    if os.environ.get("ANTHROPIC_BASE_URL"):
        return os.environ["ANTHROPIC_BASE_URL"]
    if _SETTINGS_PATH.exists():
        try:
            settings = _json.loads(_SETTINGS_PATH.read_text(encoding="utf-8"))
            return settings.get("env", {}).get("ANTHROPIC_BASE_URL")
        except Exception:
            pass
    return None


def _load_oauth_token() -> str | None:
    """Load OAuth token from Claude Code credentials."""
    creds_path = Path.home() / ".claude" / ".credentials.json"
    if creds_path.exists():
        try:
            creds = _json.loads(creds_path.read_text(encoding="utf-8"))
            return creds.get("claudeAiOauth", {}).get("accessToken")
        except Exception:
            pass
    return None


def get_anthropic_client() -> "anthropic.Anthropic":
    """Create an Anthropic client using the best available auth method."""
    import anthropic

    # Priority 1: OAuth token from Claude Code — force official API endpoint
    oauth_token = _load_oauth_token()
    if oauth_token:
        return anthropic.Anthropic(
            auth_token=oauth_token,
            base_url="https://api.anthropic.com",
        )

    # Priority 2: API key (direct or via proxy)
    api_key = _load_api_key()
    base_url = _load_base_url()
    if base_url:
        return anthropic.Anthropic(api_key=api_key, base_url=base_url)
    return anthropic.Anthropic(api_key=api_key)


def _strip_code_fences(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        end = -1 if lines[-1].strip() == "```" else len(lines)
        return "\n".join(lines[1:end])
    return text.strip()


def _load_workflows() -> dict[str, dict[str, Any]]:
    workflows = {}
    if not WORKFLOWS_DIR.exists():
        return workflows
    for f in WORKFLOWS_DIR.glob("*.yaml"):
        try:
            text = f.read_text(encoding="utf-8")
            if _yaml:
                data = _yaml.safe_load(text)
            else:
                data = _parse_yaml_simple(text)
            if data and "name" in data:
                workflows[data["name"]] = data
        except Exception:
            pass
    return workflows


def _parse_yaml_simple(text: str) -> dict[str, Any]:
    """Minimal YAML parser for workflow files (no pyyaml dependency)."""
    result: dict[str, Any] = {}
    current_list_key = ""
    current_list: list[Any] = []
    current_item: dict[str, str] = {}

    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if line.startswith("  - name:") and current_list_key == "steps":
            if current_item:
                current_list.append(current_item)
            current_item = {"name": stripped.split(":", 1)[1].strip()}
        elif line.startswith("    ") and current_item and ":" in stripped:
            k, v = stripped.split(":", 1)
            current_item[k.strip()] = v.strip()
        elif line.startswith("  - ") and current_list_key == "match_hints":
            current_list.append(stripped[2:].strip())
        elif not line.startswith(" ") and ":" in line:
            if current_list_key and current_list:
                if current_item:
                    current_list.append(current_item)
                    current_item = {}
                result[current_list_key] = current_list
                current_list = []
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if not v:
                current_list_key = k
                current_list = []
            else:
                result[k] = v

    if current_list_key:
        if current_item:
            current_list.append(current_item)
        result[current_list_key] = current_list

    return result


class AgentLoop:
    def __init__(self, verbose: bool = False) -> None:
        api_key = _load_api_key()
        base_url = _load_base_url()
        if base_url:
            self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
        self.verbose = verbose

        from .tool_manager import ToolManager
        from .reflect import Reflect
        from .blue_agent import BlueAgent
        from .benchmark.metrics import RunMetrics
        self.tm = ToolManager()
        self.reflect = Reflect(verbose=verbose, api_key=api_key, base_url=base_url)
        self.blue = BlueAgent(api_key=api_key, base_url=base_url, verbose=verbose)
        self.workflows = _load_workflows()
        self._RunMetrics = RunMetrics

        self.steps: list[dict[str, Any]] = []
        self.collected_data: list[str] = []
        self.last_output_file: str | None = None
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

    def run(self, task: str) -> dict[str, Any]:
        # Step 0: Select workflow
        workflow_name = self._select_workflow(task)
        print(f"\n[Agent] task: {task}")
        print(f"[Agent] workflow: {workflow_name}")
        print(f"[Agent] available tools: {len(self.tm.list_tools())}")

        metrics = self._RunMetrics(task=task, workflow=workflow_name)
        self._current_metrics = metrics

        # Step 1: Plan
        plan = self._plan_task(task, workflow_name)
        print(f"[Step 1] planning...")
        print(f"  -> {plan.get('approach', 'unknown')}")

        # Step 2: Execute
        step_result = self._execute_plan(task, plan)
        self.steps.append({"step": "execute", **step_result})
        metrics.steps_executed = len(plan.get("steps", []))
        print(f"[Step 2] done")

        # Step 3: Reflect
        tool_list = self._format_tool_list()
        reflection = self.reflect.assess(
            task=task,
            steps=self._format_steps(),
            tool_count=len(self.tm.list_tools()),
            tool_list=tool_list,
        )
        print(f"[Step 3] reflect")
        print(f"  -> need_new_tool: {reflection['need_new_tool']}")
        metrics.workflow_fit = reflection.get("workflow_fit", "")

        if reflection["need_new_tool"]:
            tool_spec = reflection["tool_spec"]
            print(f"  -> tool: {tool_spec['name']}")

            # Blue Agent: challenge tool creation
            blue_tool_result, blue_usage = self.blue.challenge_tool(
                tool_spec=tool_spec,
                existing_tools=self.tm.list_tools(),
                task=task,
            )
            metrics.add_token_usage(blue_usage.input_tokens, blue_usage.output_tokens)
            metrics.blue_challenges += 1
            verdict = blue_tool_result.get("verdict", "approve")
            print(f"  [Blue] tool verdict: {verdict}")

            if verdict == "block":
                print(f"  [Blue] blocked: {blue_tool_result.get('reason', '')[:80]}")
                metrics.blue_blocks += 1
            else:
                if verdict == "revise":
                    print(f"  [Blue] revise suggestion: {blue_tool_result.get('suggestion', '')[:80]}")
                self._create_tool(task, tool_spec)
                metrics.add_new_tool(tool_spec["name"])
        else:
            print(f"  -> {reflection['reasoning'][:80]}")

        # Step 4: Changelog
        self._append_changelog(reflection, task)

        # Step 5: Save report
        output_path = self._save_report(task, step_result)
        if output_path:
            print(f"[Step 5] saved: {output_path}")

            # Blue Agent: challenge report
            report_text = output_path.read_text(encoding="utf-8")
            try:
                challenges, blue_usage = self.blue.challenge_report(report_text, task)
                metrics.add_token_usage(blue_usage.input_tokens, blue_usage.output_tokens)
                metrics.blue_challenges += len(challenges)
                if challenges:
                    blue_section = self.blue.format_report_section(challenges)
                    output_path.write_text(report_text + blue_section, encoding="utf-8")
                    print(f"  [Blue] appended {len(challenges)} challenges to report")
            except Exception as e:
                print(f"  [Blue] report review failed (non-fatal): {e}")

            # Benchmark: check report structure
            from .benchmark.report_checker import check_structure
            struct = check_structure(report_text)
            metrics.structure_ok = struct.get("all_ok", False)

        # Save metrics
        metrics.save()
        print(f"[Metrics] saved to benchmark/metrics.jsonl")

        return {
            "summary": step_result.get("summary", ""),
            "workflow": workflow_name,
            "new_tool": reflection.get("tool_spec", {}).get("name") if reflection["need_new_tool"] else None,
            "output_path": str(output_path) if output_path else None,
        }

    # ── Workflow selection ────────────────────────────────────────────────

    def _select_workflow(self, task: str) -> str:
        if not self.workflows:
            return "deep-insight"

        wf_descriptions = []
        for name, wf in self.workflows.items():
            hints = ", ".join(wf.get("match_hints", []))
            wf_descriptions.append(f"- {name}: {wf.get('description', '')} (keywords: {hints})")

        prompt = f"""Select the best workflow for this task. Output ONLY the workflow name, nothing else.

Task: {task}

Available workflows:
{chr(10).join(wf_descriptions)}

If unsure, default to "deep-insight"."""

        msg = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=50,
            messages=[{"role": "user", "content": prompt}],
        )
        choice = _extract_text(msg).strip().lower().replace('"', '').replace("'", "")
        if choice in self.workflows:
            return choice
        return "deep-insight"

    # ── Plan ────────────────────────────────────────────────────────────────

    def _plan_task(self, task: str, workflow_name: str = "deep-insight") -> dict[str, Any]:
        tools_desc = self._format_tool_list()
        wf = self.workflows.get(workflow_name, {})
        wf_steps = wf.get("steps", [])
        wf_context = ""
        if wf_steps:
            step_names = [s["name"] if isinstance(s, dict) else str(s) for s in wf_steps]
            wf_context = f"\nWorkflow ({workflow_name}): {' → '.join(step_names)}\nFollow this workflow structure when planning steps.\n"

        prompt = f"""You are an AI agent. Analyze the task and plan execution steps.

Task: {task}
{wf_context}
Available tools:
{tools_desc if tools_desc.strip() else '(none)'}

Output a JSON object (no markdown fences):
{{
  "approach": "1-2 sentence plan",
  "steps": [
    {{
      "description": "what this step does",
      "tool": "tool_name or null if LLM should do it",
      "tool_args": ["arg1", "arg2"] // CLI args for the tool, empty if tool is null
    }}
  ]
}}

Important:
- For fetch_hn, tool_args should be [keyword, limit]. The keyword is a SINGLE word, no spaces.
  Example: ["Claude", "10"] or ["agent", "20"]
- For fetch_rss, tool_args should be [url, limit].
- For filter-by-date, tool_args should be ["{{prev_output_file}}", date_field, target_date, range_days].
  Use the literal string "{{prev_output_file}}" — it will be replaced with the actual file path at runtime.
  Example: ["{{prev_output_file}}", "time", "2026-05-02", "0"]
- If no tool fits, set tool to null and tool_args to [].
- Keep steps minimal (2-4 steps max)."""

        msg = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return _json.loads(_strip_code_fences(_extract_text(msg)))

    # ── Execute ─────────────────────────────────────────────────────────────

    def _execute_plan(self, task: str, plan: dict[str, Any]) -> dict[str, Any]:
        steps = plan.get("steps", [])
        all_output = []
        prev_output = ""

        for i, step in enumerate(steps):
            desc = step.get("description", str(step)) if isinstance(step, dict) else str(step)
            tool_name = step.get("tool") if isinstance(step, dict) else None
            tool_args = step.get("tool_args", []) if isinstance(step, dict) else []

            print(f"  [{i+1}/{len(steps)}] {desc}")
            output = self._execute_single_step(task, desc, tool_name, tool_args, prev_output)
            all_output.append(f"Step {i+1}: {desc}\n{output}")
            prev_output = output

        return {"summary": "\n\n".join(all_output), "details": all_output, "raw_data": prev_output}

    def _execute_single_step(
        self, task: str, step_desc: str, tool_name: str | None,
        tool_args: list[str], prev_output: str,
    ) -> str:
        if tool_name and tool_name != "null" and self.tm.find_tool(tool_name):
            # If tool_args reference "{prev_output_file}", substitute the actual path
            resolved_args = []
            for a in (str(x) for x in tool_args):
                if a == "{prev_output_file}" and self.last_output_file:
                    resolved_args.append(self.last_output_file)
                else:
                    resolved_args.append(a)

            print(f"    -> tool: {tool_name} {resolved_args}")
            rc, out, err = self.tm.execute(tool_name, resolved_args)
            if hasattr(self, '_current_metrics'):
                self._current_metrics.add_tool_used(tool_name)
            if rc != 0:
                print(f"    -> FAILED: {err[:150]}")
                return f"[tool {tool_name} failed: {err[:200]}]"

            # Save output to temp file for next step
            out = out or ""
            tmp = TEMP_DIR / f"step_output.json"
            tmp.write_text(out, encoding="utf-8")
            self.last_output_file = str(tmp)

            self.collected_data.append(out)
            print(f"    -> OK, {len(out)} chars")
            return out

        print(f"    -> LLM")
        return self._llm_execute(task, step_desc, prev_output)

    def _llm_execute(self, task: str, step: str, prev_output: str) -> str:
        context = f"\n\nPrevious step output:\n{prev_output[:3000]}" if prev_output else ""
        prompt = f"""You are an agent executing a task step by step.

Task: {task}
Current step: {step}{context}

Execute this step. Output ONLY the result data (JSON, text, or summary).
Do NOT explain your reasoning. Do NOT wrap in code fences.
If the previous step provided data, use that data — do NOT fabricate new data."""

        msg = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        return _strip_code_fences(_extract_text(msg))

    # ── Tool creation ──────────────────────────────────────────────────────

    def _create_tool(self, task: str, tool_spec: dict[str, Any]) -> None:
        print(f"[Step 4] creating tool: {tool_spec['name']}")
        script = self.reflect.generate_tool(task, tool_spec)

        tool_path = ROOT / "tools" / f"{tool_spec['name']}.py"
        tool_path.write_text(script + "\n", encoding="utf-8")
        print(f"  -> wrote: {tool_path.relative_to(ROOT)}")

        self.tm.register(
            name=tool_spec["name"],
            description=tool_spec.get("description", ""),
            path=f"tools/{tool_spec['name']}.py",
            language=tool_spec.get("language", "python"),
            args_schema=tool_spec.get("args_schema", ""),
        )
        print(f"  -> registered: {tool_spec['name']}")

    # ── Changelog ──────────────────────────────────────────────────────────

    def _append_changelog(self, reflection: dict[str, Any], task: str) -> None:
        changelog_path = ROOT / "changelog.md"
        today = date.today().isoformat()
        action = "create" if reflection["need_new_tool"] else "reflect"
        tool_name = reflection.get("tool_spec", {}).get("name", "-") if reflection.get("tool_spec") else "-"
        reason = reflection.get("reasoning", "-")[:120]

        line = f"| {today} | {action} | {tool_name} | {reason} | task: {task[:50]} |\n"

        if changelog_path.exists():
            content = changelog_path.read_text(encoding="utf-8")
        else:
            content = "# Agent Evolution Changelog\n\n| Date | Action | Tool | Reason | Context |\n|------|--------|------|--------|---------|\n"

        changelog_path.write_text(content + line, encoding="utf-8")

    # ── Report ─────────────────────────────────────────────────────────────

    def _save_report(self, task: str, step_result: dict[str, Any]) -> Path | None:
        report_dir = ROOT.parent / "data" / "reports"
        report_dir.mkdir(parents=True, exist_ok=True)
        today = date.today().isoformat()

        # Find next sequence number for today
        existing = sorted(report_dir.glob(f"{today}-from-b-agent-*.md"))
        if existing:
            last = existing[-1].stem  # e.g. "2026-05-02-from-b-agent-03"
            last_seq = int(last.rsplit("-", 1)[-1])
            seq = last_seq + 1
        else:
            seq = 1
        filename = f"{today}-from-b-agent-{seq:02d}.md"
        report_path = report_dir / filename

        raw_data = step_result.get("raw_data", "") or step_result.get("summary", "")
        all_collected = "\n\n".join(self.collected_data) if self.collected_data else raw_data

        prompt = f"""请根据以下数据生成一份中文洞察报告（Markdown 格式）。

用户的原始任务描述（非常重要，报告的结构和内容必须忠实于用户的要求）：
{task}

日期：{today}

Agent 采集的原始数据：
{all_collected[:6000]}

报告生成规则：
1. 仔细阅读用户的任务描述，按用户要求的结构和视角来组织报告
2. 如果用户要求了特定章节、视角（如蓝军视角）、分析方式，必须在报告中体现
3. 如果用户没有指定特殊格式，使用以下默认格式：

# Daily Brief — {today}

> 一句话摘要
>
> 数据源：N 个 / 已扫条目：M / 入选条目：K

## 最关注的事
### 1. <标题>
<2-4 句说明>
来源：[<原文标题>](<URL>)

## 值得一看的事
- <一句话> — [<源>](<URL>)

## 今日观察小结

4. 全文使用中文
5. 所有 URL 必须来自上面的原始数据，绝对不要编造 URL
6. 原文标题保留英文原文即可
7. 如果数据不足，使用兜底文案："今日无重要事件"
- 直接输出 Markdown 内容，不要有代码块标记"""

        msg = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        report = _strip_code_fences(_extract_text(msg))
        report_path.write_text(report + "\n", encoding="utf-8")
        return report_path

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _format_tool_list(self) -> str:
        tools = self.tm.list_tools()
        if not tools:
            return ""
        lines = []
        for t in tools:
            lines.append(f"- {t['name']}: {t['description']} (args: {t.get('args_schema', 'N/A')})")
        return "\n".join(lines)

    def _format_steps(self) -> str:
        if not self.steps:
            return "(no steps yet)"
        parts = []
        for s in self.steps:
            details = s.get("details", [])
            parts.append(f"- {s.get('step', '')}: {'; '.join(str(d)[:100] for d in details)}")
        return "\n".join(parts)
