#!/usr/bin/env python3
"""
CLI entry point for the DeepInsight agent.

Usage:
    python -m agent "your task description"
    python -m agent --workflow daily-radar
    python -m agent --workflow deep-read --url "https://..."
    python -m agent --workflow topic-research --keyword "agentic SE"
    python -m agent --list-workflows
    python -m agent --list-steps
"""

import argparse
import sys
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parent
WORKFLOWS_DIR = ROOT / "workflows"


def main() -> None:
    parser = argparse.ArgumentParser(description="DeepInsight Agent")
    parser.add_argument("task", nargs="?", help="Task description (legacy mode)")
    parser.add_argument("--workflow", "-w", help="Workflow name (e.g. daily-radar)")
    parser.add_argument("--dry-run", action="store_true", help="Print execution plan without running")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed logs")
    parser.add_argument("--url", help="URL parameter for deep-read workflow")
    parser.add_argument("--keyword", help="Keyword parameter for topic-research workflow")
    parser.add_argument("--skip-blue", action="store_true", help="Skip blue agent critique step")
    parser.add_argument("--list-workflows", action="store_true", help="List available workflows")
    parser.add_argument("--list-steps", action="store_true", help="List registered steps")
    parser.add_argument(
        "--cedar-mode", choices=["off", "shadow", "enforce"], default=None,
        help="Cedar 闸门模式(默认:env DEEPINSIGHT_CEDAR_MODE 或 shadow)",
    )
    args = parser.parse_args()

    if args.list_workflows:
        _list_workflows()
        return

    if args.list_steps:
        _list_steps()
        return

    if args.workflow:
        _run_workflow(args)
        return

    if args.task:
        _run_legacy(args)
        return

    parser.print_help()


def _run_workflow(args: argparse.Namespace) -> None:
    # Register all steps
    from . import steps  # noqa: F401
    from .pipeline import PipelineEngine

    workflow_path = WORKFLOWS_DIR / f"{args.workflow}.yaml"
    if not workflow_path.exists():
        print(f"[Error] Workflow '{args.workflow}' not found at {workflow_path}", file=sys.stderr)
        print(f"Available: {', '.join(w.stem for w in WORKFLOWS_DIR.glob('*.yaml'))}")
        sys.exit(1)

    engine = PipelineEngine(verbose=args.verbose, cedar_mode=args.cedar_mode)
    task = args.keyword or args.url or args.workflow
    kwargs = {}
    if args.url:
        kwargs["url"] = args.url
    if args.keyword:
        kwargs["keyword"] = args.keyword
    if args.skip_blue:
        kwargs["skip_blue"] = True

    ctx = engine.run(workflow_path, task=task, dry_run=args.dry_run, **kwargs)

    if not args.dry_run and ctx.has("output_path"):
        print(f"\nOutput: {ctx.get('output_path')}")


def _run_legacy(args: argparse.Namespace) -> None:
    from .loop import AgentLoop, _load_api_key

    try:
        _load_api_key()
    except ValueError as e:
        print(f"[Error] {e}", file=sys.stderr)
        sys.exit(1)

    loop = AgentLoop(verbose=args.verbose)
    result = loop.run(args.task)

    if result.get("error"):
        print(f"\n[Error] {result['error']}", file=sys.stderr)
        sys.exit(1)
    else:
        print(f"\n[Done] {result['summary']}")


def _list_workflows() -> None:
    print("Available workflows:")
    for f in sorted(WORKFLOWS_DIR.glob("*.yaml")):
        try:
            import yaml
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
        except ImportError:
            data = {"name": f.stem, "description": ""}
            for line in f.read_text(encoding="utf-8").splitlines()[:3]:
                if line.startswith("description:"):
                    data["description"] = line.split(":", 1)[1].strip()
        name = data.get("name", f.stem)
        desc = data.get("description", "")
        print(f"  {name:20s} {desc}")


def _list_steps() -> None:
    from . import steps  # noqa: F401
    from .pipeline import StepRegistry

    print("Registered steps:")
    for name in sorted(StepRegistry.list_all()):
        print(f"  {name}")


if __name__ == "__main__":
    main()
