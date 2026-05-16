#!/usr/bin/env python3
"""
BlueAgent — adversarial review module for reports and tool creation decisions.
"""

import json
import time
from pathlib import Path
from typing import Any

import anthropic


def _extract_text(msg) -> str:
    for block in msg.content:
        if hasattr(block, "text"):
            return block.text
    return ""

ROOT = Path(__file__).resolve().parent  # agent/
PROJECT_ROOT = ROOT.parent
PROMPT_BLUE_REPORT = PROJECT_ROOT / "prompts" / "blue_report.md"
PROMPT_BLUE_TOOL = PROJECT_ROOT / "prompts" / "blue_tool.md"


def _load_prompt(path: Path, **kwargs: str) -> str:
    return path.read_text(encoding="utf-8").format(**kwargs)


def _strip_fences(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```"):
        end = -1 if lines[-1].strip() == "```" else len(lines)
        return "\n".join(lines[1:end])
    return text.strip()


def _parse_json(text: str) -> Any:
    text = _strip_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("[") if text.find("[") < text.find("{") or text.find("{") < 0 else text.find("{")
        if start < 0:
            start = text.find("{")
        if start < 0:
            return []
        bracket = text[start]
        close = "]" if bracket == "[" else "}"
        end = text.rfind(close) + 1
        if end > start:
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                pass
    return []


class BlueAgent:
    def __init__(self, api_key: str = "", base_url: str | None = None, verbose: bool = False, client: anthropic.Anthropic | None = None) -> None:
        if client:
            self.client = client
        elif base_url:
            self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
        self.verbose = verbose

    def _call(self, **kwargs) -> Any:
        for attempt in range(5):
            try:
                return self.client.messages.create(**kwargs)
            except anthropic.RateLimitError:
                wait = 2 ** attempt * 5
                if self.verbose:
                    print(f"    [blue agent rate limited, waiting {wait}s...]")
                time.sleep(wait)
        raise RuntimeError("Rate limit exceeded after 5 retries")

    def challenge_report(self, report_text: str, task: str) -> tuple[list[dict[str, Any]], Any]:
        prompt = _load_prompt(PROMPT_BLUE_REPORT, report=report_text[:6000], task=task)
        if self.verbose:
            print("[Blue] reviewing report...")

        msg = self._call(
            model="claude-haiku-4-5-20251001",
            max_tokens=2048,
            messages=[{"role": "user", "content": prompt}],
        )
        challenges = _parse_json(_extract_text(msg))
        if not isinstance(challenges, list):
            challenges = [challenges] if challenges else []

        if self.verbose:
            print(f"[Blue] {len(challenges)} challenges")
        return challenges, msg.usage

    def challenge_tool(
        self, tool_spec: dict[str, Any], existing_tools: list[dict[str, Any]], task: str
    ) -> tuple[dict[str, Any], Any]:
        tools_desc = "\n".join(
            f"- {t['name']}: {t['description']} (usage: {t.get('usage_count', 0)})"
            for t in existing_tools
        )
        spec_str = json.dumps(tool_spec, ensure_ascii=False, indent=2)
        prompt = _load_prompt(
            PROMPT_BLUE_TOOL, tool_spec=spec_str, existing_tools=tools_desc, task=task
        )
        if self.verbose:
            print(f"[Blue] reviewing tool: {tool_spec.get('name', '?')}")

        msg = self._call(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        result = _parse_json(_extract_text(msg))
        if isinstance(result, list):
            result = result[0] if result else {"verdict": "approve", "reason": "parse error"}
        if not isinstance(result, dict):
            result = {"verdict": "approve", "reason": "parse error"}

        if self.verbose:
            print(f"[Blue] verdict: {result.get('verdict', '?')}")
        return result, msg.usage

    @staticmethod
    def format_report_section(challenges: list[dict[str, Any]]) -> str:
        if not challenges:
            return ""
        lines = ["\n---\n", "## 蓝军反驳（Blue Agent 自动生成）\n"]
        for i, c in enumerate(challenges, 1):
            target = c.get("target", "未知章节")
            lines.append(f"### 反驳 #{i}（针对 {target}）\n")
            original = c.get("original_claim", "")
            if original:
                lines.append(f"**原文观点**：{original}\n")
            challenge = c.get("challenge", "")
            if challenge:
                lines.append(f"**蓝军视角分析**：{challenge}\n")
            alt = c.get("alternative_view", "")
            if alt:
                lines.append(f"**替代视角**：{alt}\n")
            lines.append("")
        return "\n".join(lines)
