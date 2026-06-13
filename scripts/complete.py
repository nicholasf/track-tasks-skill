#!/usr/bin/env python3
import argparse
import re
import sys
from datetime import date
from pathlib import Path

from workflow import TaskState, transition


def _read_status(content: str) -> TaskState:
    m = re.search(r'^\*\*Status:\*\*\s*(.+)$', content, re.MULTILINE)
    if not m:
        raise ValueError('No **Status:** field found in task file')
    raw = m.group(1).strip()
    if raw == 'planned':
        return TaskState.pending
    return TaskState(raw)


def _read_title(content: str) -> str:
    m = re.search(r'^# (.+)$', content, re.MULTILINE)
    return m.group(1).strip() if m else 'Untitled'


def _set_status(content: str, new_status: TaskState) -> str:
    return re.sub(
        r'^\*\*Status:\*\*\s*.+$',
        f'**Status:** {new_status}',
        content,
        flags=re.MULTILINE,
    )


def _fill_results(content: str, summary: str, tests: str, files_changed: str) -> str:
    results_block = (
        f'## Results\n'
        f'**Tests:** {tests}\n'
        f'**Files changed:** {files_changed}\n'
        f'**Summary:** {summary}\n'
    )
    return re.sub(
        r'^## Results\b.*',
        results_block,
        content,
        flags=re.MULTILINE | re.DOTALL,
    )


def _append_dev_log(dev_log_path: Path, title: str, summary: str) -> None:
    today = date.today().isoformat()
    entry = f'\n## {today} — {title}\n\n- {summary}\n'
    with dev_log_path.open('a') as f:
        f.write(entry)


def complete_task(
    task_path: Path,
    summary: str,
    tests: str,
    files_changed: str,
    cwd: Path,
) -> Path:
    content = task_path.read_text()
    current = _read_status(content)
    transition(current, TaskState.completed)

    title = _read_title(content)
    content = _set_status(content, TaskState.completed)
    content = _fill_results(content, summary, tests, files_changed)

    completed_dir = cwd / 'tasks' / 'completed'
    completed_dir.mkdir(parents=True, exist_ok=True)
    dest = completed_dir / task_path.name
    dest.write_text(content)
    task_path.unlink()

    dev_log_path = cwd / 'development-log.md'
    if dev_log_path.exists():
        _append_dev_log(dev_log_path, title, summary)

    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description='Mark a task as completed')
    parser.add_argument('task', help='Path to the task file')
    parser.add_argument('--summary', required=True, help='What was done')
    parser.add_argument('--tests', required=True, help='Test outcome')
    parser.add_argument('--files-changed', required=True, help='Files changed')
    parser.add_argument('--cwd', default=None, help='Project root (default: tasks/ grandparent)')
    args = parser.parse_args()

    task_path = Path(args.task).resolve()
    cwd = Path(args.cwd).resolve() if args.cwd else task_path.parent.parent.parent

    try:
        dest = complete_task(task_path, args.summary, args.tests, args.files_changed, cwd)
    except (ValueError, FileNotFoundError) as error:
        print(f'[complete] {error}', file=sys.stderr)
        sys.exit(1)

    print(dest)


if __name__ == '__main__':
    main()
