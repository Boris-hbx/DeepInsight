#!/usr/bin/env python3
"""
Reflect module — calls Claude API to assess step results and decide tool needs.
"""


def _extract_text(msg) -> str:
    for block in msg.content:
        if hasattr(block, "text"):
            return block.text
    return ""

import json
from pathlib import Path
from typing import Any

import anthropic

ROOT = Path(__file__).resolve().parent  # agent/
PROJECT_ROOT = ROOT.parent
PROMPT_REFLECT = PROJECT_ROOT / "prompts" / "reflect.md"


def _load_prompt(template_path: Path, **kwargs: str) -> str:
    return template_path.read_text(encoding="utf-8").format(**kwargs)


class Reflect:
    def __init__(self, verbose: bool = False, api_key: str | None = None, base_url: str | None = None) -> None:
        if not api_key:
            raise ValueError("api_key is required")
        if base_url:
            self.client = anthropic.Anthropic(api_key=api_key, base_url=base_url)
        else:
            self.client = anthropic.Anthropic(api_key=api_key)
        self.verbose = verbose

    def assess(
        self,
        task: str,
        steps: str,
        tool_count: int,
        tool_list: str,
    ) -> dict[str, Any]:
        prompt = _load_prompt(
            PROMPT_REFLECT,
            task=task,
            steps=steps,
            tool_count=tool_count,
            tool_list=tool_list,
        )
        if self.verbose:
            print(f"\n[Reflect] calling Claude API...")

        msg = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = _extract_text(msg).strip()
        if self.verbose:
            print(f"[Reflect] raw response:\n{text[:500]}")

        # Parse JSON from response
        return self._parse_response(text)

    def _parse_response(self, text: str) -> dict[str, Any]:
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        # Try to extract JSON from text (LLM sometimes adds prose around it)
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                result = json.loads(text[start:end])
            else:
                return {"step_assessment": text[:200], "need_new_tool": False, "reasoning": "Failed to parse reflection JSON", "tool_spec": None}

        required = ["step_assessment", "need_new_tool", "reasoning"]
        for key in required:
            if key not in result:
                result.setdefault(key, "" if key != "need_new_tool" else False)
        result.setdefault("workflow_fit", "good")
        result.setdefault("workflow_note", "")

        return result

    def generate_tool(self, task: str, tool_spec: dict[str, Any]) -> str:
        prompt_path = PROJECT_ROOT / "prompts" / "create_tool.md"
        tool_spec_json = json.dumps(tool_spec, ensure_ascii=False, indent=2)
        base_prompt = _load_prompt(prompt_path, tool_spec=tool_spec_json, task=task)

        max_attempts = 3
        last_error = ""
        for attempt in range(max_attempts):
            if attempt == 0:
                prompt = base_prompt
            else:
                prompt = (
                    f"{base_prompt}\n\n"
                    f"## 上次生成失败\n\n"
                    f"上次生成的脚本有语法错误：{last_error}\n"
                    f"请只输出纯 Python 代码，不要有任何自然语言说明、markdown 标记或代码块符号。"
                )

            if self.verbose:
                print(f"\n[GenerateTool] attempt {attempt + 1}/{max_attempts}...")

            msg = self.client.messages.create(
                model="claude-opus-4-6",
                max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            script = self._clean_script(_extract_text(msg))

            error = self._validate_syntax(script)
            if error is None:
                if self.verbose:
                    print(f"[GenerateTool] OK, {len(script)} chars")
                return script

            last_error = error
            if self.verbose:
                print(f"[GenerateTool] syntax error: {error[:120]}")

        if self.verbose:
            print(f"[GenerateTool] all {max_attempts} attempts failed, returning last script")
        return script

    @staticmethod
    def _clean_script(text: str) -> str:
        script = text.strip()
        lines = script.splitlines()
        if lines and lines[0].startswith("```"):
            end = -1 if lines[-1].strip() == "```" else len(lines)
            script = "\n".join(lines[1:end])
        # Strip leading prose lines before the first Python line
        cleaned = []
        found_code = False
        for line in script.splitlines():
            if not found_code:
                stripped = line.strip()
                if stripped.startswith(("#!", "import ", "from ", "def ", "class ", '"""', "'''")) or stripped == "":
                    found_code = True
                else:
                    continue
            cleaned.append(line)
        return "\n".join(cleaned) if cleaned else script

    @staticmethod
    def _validate_syntax(script: str) -> str | None:
        try:
            compile(script, "<generated_tool>", "exec")
            return None
        except SyntaxError as e:
            return f"line {e.lineno}: {e.msg}"