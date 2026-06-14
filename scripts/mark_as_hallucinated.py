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


def _add_hallucinated_by(content: str, hallucinated_by: str) -> str:
    return re.sub(
        r'(\*\*Status:\*\*[^\n]*\n)',
        f'\\1**Hallucinated by:** {hallucinated_by}\n',
        content,
        count=1,
    )


def _fill_results(content: str, solution: str) -> str:
    results_block = (
        f'## Results\n'
        f'**Hallucinated solution:**\n\n{solution}\n'
    )
    return re.sub(
        r'^## Results\b.*',
        results_block,
        content,
        flags=re.MULTILINE | re.DOTALL,
    )


def _append_dev_log(dev_log_path: Path, title: str, solution: str) -> None:
    today = date.today().isoformat()
    entry = f'\n## {today} — {title} (hallucinated)\n\n- {solution}\n'
    with dev_log_path.open('a') as f:
        f.write(entry)


def mark_as_hallucinated(
    task_path: Path,
    solution: str,
    hallucinated_by: str,
    cwd: Path,
) -> Path:
    content = task_path.read_text()
    current = _read_status(content)
    transition(current, TaskState.hallucinated)

    title = _read_title(content)
    content = _set_status(content, TaskState.hallucinated)
    if hallucinated_by:
        content = _add_hallucinated_by(content, hallucinated_by)
    content = _fill_results(content, solution)

    hallucinated_dir = cwd / 'tasks' / 'hallucinated'
    hallucinated_dir.mkdir(parents=True, exist_ok=True)
    dest = hallucinated_dir / task_path.name
    dest.write_text(content)
    task_path.unlink()

    dev_log_path = cwd / 'development-log.md'
    if dev_log_path.exists():
        _append_dev_log(dev_log_path, title, solution)

    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description='Mark a task as hallucinated')
    parser.add_argument('task', help='Path to the task file')
    parser.add_argument('--solution', required=True, help='The full solution the LLM claimed to have produced')
    parser.add_argument('--hallucinated-by', default='', help='Agent or model that hallucinated this task')
    parser.add_argument('--cwd', default=None, help='Project root (default: tasks/ grandparent)')
    args = parser.parse_args()

    task_path = Path(args.task).resolve()
    cwd = Path(args.cwd).resolve() if args.cwd else task_path.parent.parent.parent

    try:
        dest = mark_as_hallucinated(task_path, args.solution, args.hallucinated_by, cwd)
    except (ValueError, FileNotFoundError) as error:
        print(f'[mark_as_hallucinated] {error}', file=sys.stderr)
        sys.exit(1)

    print(dest)


if __name__ == '__main__':
    main()
