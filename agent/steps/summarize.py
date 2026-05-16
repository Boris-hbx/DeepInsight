"""summarize — LLM report generation with multiple styles."""

from __future__ import annotations

import json
import time
from datetime import date
from typing import Any

import anthropic

from ..pipeline.step import Step, StepRegistry
from ..pipeline.context import PipelineContext

STYLES = {
    "daily-brief": """请根据以下数据生成一份中文洞察报告（Markdown 格式）。

日期：{date}

数据：
{data}

报告格式：
# Daily Brief — {date}

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

规则：
- 全文中文
- URL 必须来自原始数据，不要编造
- 原文标题保留英文原文
- 数据不足时写"今日无重要事件"
- 直接输出 Markdown，不要代码块标记""",

    "deep-analysis": """请对以下内容进行深度分析，生成结构化报告（中文 Markdown）。

原文：
{data}

报告结构：
# 深度阅读：<标题>

## 核心论点
<作者的中心主张>

## 方法论 / 技术路线
<作者怎么论证的>

## 关键发现
- ...

## 可借鉴的点
<对我们项目 / 实践的启发>

## 局限性
<论证中的薄弱环节>

规则：
- 全文中文
- 保持客观，区分事实和观点
- 直接输出 Markdown""",

    "research-synthesis": """请综合以下多源数据，生成一份主题研究报告（中文 Markdown）。

主题：{topic}
日期：{date}

多源数据：
{data}

报告结构：
# 主题研究：{topic}

## 概览
<3-5 句总结>

## 主要发现
### 1. <主题>
<来源 + 说明>

## 多方视角对比
<不同来源的观点差异>

## 趋势判断
<基于数据的趋势推断>

## 参考来源
- [标题](URL)

规则：
- 全文中文
- URL 必须来自原始数据
- 综合而非简单罗列""",
}


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
class SummarizeStep(Step):
    name = "summarize"

    def run(self, ctx: PipelineContext) -> None:
        style = self.config.get("style", "daily-brief")
        language = self.config.get("language", "zh")

        # Get input data
        input_data = ctx.get(self.inputs[0]) if self.inputs else ""
        if isinstance(input_data, list):
            data_str = json.dumps(input_data[:30], ensure_ascii=False, indent=1)[:6000]
        elif isinstance(input_data, dict):
            data_str = input_data.get("text", json.dumps(input_data, ensure_ascii=False))[:8000]
        else:
            data_str = str(input_data)[:8000]

        # Build prompt
        template = STYLES.get(style, STYLES["daily-brief"])
        today = date.today().isoformat()
        prompt = template.format(
            data=data_str,
            date=today,
            topic=ctx.metadata.get("keyword", ctx.metadata.get("task", "")),
        )

        client = _get_client()
        msg = _call_with_retry(
            client,
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        report = msg.content[0].text.strip()
        if report.startswith("```"):
            lines = report.splitlines()
            report = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])

        output_name = self.outputs[0] if self.outputs else "report_md"
        ctx.put(output_name, report)
        print(f"    -> report generated ({len(report)} chars)")
