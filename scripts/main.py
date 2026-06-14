#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path

import show as show_mod
from create import select_tokenizer, create_task
from complete import complete_task
from deprecate import deprecate_task
from mark_as_hallucinated import mark_as_hallucinated
from preflight import run_preflight, append_preflight


def _cmd_create(args: argparse.Namespace) -> None:
    import os
    cwd = args.cwd or os.getcwd()
    try:
        if args.input:
            task_fields = json.loads(Path(args.input).read_text())
        else:
            task_fields = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as error:
        print(f'[create] could not read task JSON: {error}', file=sys.stderr)
        sys.exit(1)

    tokenizer, tokenizer_source = select_tokenizer(args.local, args.hostname, args.backend, args.model)
    try:
        task_path = create_task(
            task_fields=task_fields,
            tokenizer=tokenizer,
            tokenizer_source=tokenizer_source,
            hostname=args.hostname,
            backend=args.backend,
            agent_name=args.agent,
            model=args.model,
            cwd=cwd,
        )
    except Exception as error:
        print(f'[create] {error}', file=sys.stderr)
        sys.exit(1)
    print(task_path)


def _cmd_complete(args: argparse.Namespace) -> None:
    task_path = Path(args.task).resolve()
    cwd = Path(args.cwd).resolve() if args.cwd else task_path.parent.parent.parent
    try:
        dest = complete_task(task_path, args.summary, args.tests, args.files_changed, cwd)
    except (ValueError, FileNotFoundError) as error:
        print(f'[complete] {error}', file=sys.stderr)
        sys.exit(1)
    print(dest)


def _cmd_deprecate(args: argparse.Namespace) -> None:
    task_path = Path(args.task).resolve()
    cwd = Path(args.cwd).resolve() if args.cwd else task_path.parent.parent.parent
    try:
        dest = deprecate_task(task_path, args.reason, args.deprecated_by, cwd)
    except (ValueError, FileNotFoundError) as error:
        print(f'[deprecate] {error}', file=sys.stderr)
        sys.exit(1)
    print(dest)


def _cmd_mark_as_hallucinated(args: argparse.Namespace) -> None:
    task_path = Path(args.task).resolve()
    cwd = Path(args.cwd).resolve() if args.cwd else task_path.parent.parent.parent
    try:
        dest = mark_as_hallucinated(
            task_path,
            args.solution,
            args.hallucinating_agent_handle,
            args.reporter,
            args.reason,
            cwd,
        )
    except (ValueError, FileNotFoundError) as error:
        print(f'[mark-as-hallucinated] {error}', file=sys.stderr)
        sys.exit(1)
    print(dest)


def _cmd_show(args: argparse.Namespace) -> None:
    import sys as _sys
    root = Path(args.cwd) if args.cwd else Path.cwd()
    task_dir = root / 'tasks' / args.state

    if not task_dir.exists():
        print(f'Directory not found: {task_dir}', file=_sys.stderr)
        _sys.exit(1)

    files = sorted(task_dir.glob('*.md'))
    total = len(files)
    start = (args.page - 1) * args.per_page
    page_files = files[start: start + args.per_page]

    if not page_files and args.page > 1:
        total_pages = max(1, (total + args.per_page - 1) // args.per_page)
        print(f'Page {args.page} out of range (total pages: {total_pages}).', file=_sys.stderr)
        _sys.exit(1)

    tasks = [t for f in page_files if (t := show_mod.parse_task(f))]
    summary = show_mod.closed_summary(root)
    show_mod.print_table(tasks, args.state, args.page, args.per_page, total, summary)


def _cmd_preflight(args: argparse.Namespace) -> None:
    try:
        preflight = run_preflight(
            task_path=args.task,
            hostname=args.hostname,
            backend=args.backend,
            agent_name=args.agent,
            model=args.model,
            cwd=args.cwd,
        )
    except Exception as error:
        print(f'[preflight] {error}', file=sys.stderr)
        sys.exit(1)
    print(preflight)
    if args.write:
        append_preflight(args.task, preflight)
        print(f'Pre-flight section written to {args.task}', file=sys.stderr)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog='main.py',
        description='Task tracking CLI — create, complete, deprecate, and inspect tasks.',
    )
    sub = parser.add_subparsers(dest='subcommand', metavar='subcommand')
    sub.required = True

    # ── create ────────────────────────────────────────────────────────────────
    p = sub.add_parser('create', help='Create a new task file with preflight estimation')
    p.add_argument('--input', help='JSON file path (default: read from stdin)')
    p.add_argument('--hostname', default='', help='Inference node hostname')
    p.add_argument('--backend', default='llama-server', choices=['llama-server', 'ollama'])
    p.add_argument('--agent', default='hermes', help='Agent name for reasoning buffer lookup')
    p.add_argument('--model', default='', help='Model name for tok/s lookup')
    p.add_argument('--local', action='store_true', help='Force local tokenizer')
    p.add_argument('--cwd', default=None, help='Project root directory')
    p.set_defaults(func=_cmd_create)

    # ── complete ──────────────────────────────────────────────────────────────
    p = sub.add_parser('complete', help='Mark a task as completed')
    p.add_argument('task', help='Path to the task file')
    p.add_argument('--summary', required=True, help='What was done')
    p.add_argument('--tests', required=True, help='Test outcome')
    p.add_argument('--files-changed', required=True, dest='files_changed', help='Files changed')
    p.add_argument('--cwd', default=None, help='Project root')
    p.set_defaults(func=_cmd_complete)

    # ── deprecate ─────────────────────────────────────────────────────────────
    p = sub.add_parser('deprecate', help='Mark a task as deprecated')
    p.add_argument('task', help='Path to the task file')
    p.add_argument('--reason', required=True, help='Why this task is being deprecated')
    p.add_argument('--deprecated-by', default='', dest='deprecated_by',
                   help='Slug or path of the replacing task')
    p.add_argument('--cwd', default=None, help='Project root')
    p.set_defaults(func=_cmd_deprecate)

    # ── mark-as-hallucinated ──────────────────────────────────────────────────
    p = sub.add_parser('mark-as-hallucinated', help='Mark a task as hallucinated by an LLM')
    p.add_argument('task', help='Path to the task file')
    p.add_argument('--solution', required=True, help='Full solution the LLM claimed to produce')
    p.add_argument('--hallucinating-agent-handle', default='',
                   dest='hallucinating_agent_handle',
                   help='Agent handle that produced the hallucination')
    p.add_argument('--reporter', default='', help='Agent handle that judged this a hallucination')
    p.add_argument('--reason', default='', help='Why this was judged as a hallucination')
    p.add_argument('--cwd', default=None, help='Project root')
    p.set_defaults(func=_cmd_mark_as_hallucinated)

    # ── show ──────────────────────────────────────────────────────────────────
    p = sub.add_parser('show', help='Show a summary table of task files')
    p.add_argument('state', nargs='?', default='pending',
                   choices=['pending', 'completed', 'deprecated', 'hallucinated'],
                   help='Task bucket to display (default: pending)')
    p.add_argument('--page', type=int, default=1, help='Page number (default: 1)')
    p.add_argument('--per-page', type=int, default=20, dest='per_page',
                   help='Tasks per page (default: 20)')
    p.add_argument('--cwd', default=None, help='Project root directory')
    p.set_defaults(func=_cmd_show)

    # ── preflight ─────────────────────────────────────────────────────────────
    p = sub.add_parser('preflight', help='Compute a preflight token estimate for a task')
    p.add_argument('task', help='Path to the task file')
    p.add_argument('--hostname', required=True, help='Inference node hostname')
    p.add_argument('--backend', default='llama-server', choices=['llama-server', 'ollama'],
                   help='Inference backend (default: llama-server)')
    p.add_argument('--agent', default='hermes',
                   help='Agent name in topology Agent State (default: hermes)')
    p.add_argument('--model', default='', help='Model name (required for Ollama)')
    p.add_argument('--cwd', default=None, help='Base directory for resolving task file paths')
    p.add_argument('--write', action='store_true',
                   help='Write the preflight section back to the task file')
    p.set_defaults(func=_cmd_preflight)

    args = parser.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
