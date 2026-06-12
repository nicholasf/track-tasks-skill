#!/usr/bin/env python3
"""
show.py — print a formatted summary table of task files.

Usage:
  show.py [pending|completed|deprecated] [--page N] [--per-page N] [--cwd DIR]
"""

import argparse
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path


def parse_task(path: Path) -> dict:
    try:
        text = path.read_text()
    except OSError:
        return {}

    title_m = re.search(r'^# (.+)$', text, re.MULTILINE)
    title = title_m.group(1).strip() if title_m else '(no title)'

    status_m = re.search(r'^\*\*Status:\*\*\s*(.+)$', text, re.MULTILINE)
    status = status_m.group(1).strip() if status_m else '—'

    created_m = re.search(r'^\*\*Created:\*\*\s*(.+)$', text, re.MULTILINE)
    created_raw = created_m.group(1).strip() if created_m else '—'
    # Normalise to YYYY-MM-DD; fall back to timestamp prefix in filename
    date_m = re.match(r'(\d{4}-\d{2}-\d{2})', created_raw)
    if date_m:
        created = date_m.group(1)
    else:
        ts_m = re.match(r'(\d{4}-\d{2}-\d{2})', path.stem)
        created = ts_m.group(1) if ts_m else '—'

    model_m = re.search(r'^\*\*Model:\*\*\s*(.+)$', text, re.MULTILINE)
    model_full = model_m.group(1).strip() if model_m else '—'
    # Keep just the model name — strip everything after " on " or " — "
    model = re.split(r'\s+(?:on|—)\s+', model_full)[0].strip()

    return {
        'title': title,
        'status': status,
        'created': created,
        'model': model,
    }


def closed_summary(root: Path) -> str:
    """Return a one-line summary of completed + deprecated task counts and span."""
    dates: list[date] = []
    counts: dict[str, int] = {'completed': 0, 'deprecated': 0}

    for bucket in ('completed', 'deprecated'):
        bucket_dir = root / 'tasks' / bucket
        if not bucket_dir.exists():
            continue
        for path in bucket_dir.glob('*.md'):
            counts[bucket] += 1
            task = parse_task(path)
            created = task.get('created', '—')
            m = re.match(r'(\d{4}-\d{2}-\d{2})', created)
            if m:
                try:
                    dates.append(datetime.strptime(m.group(1), '%Y-%m-%d').date())
                except ValueError:
                    pass

    total_closed = counts['completed'] + counts['deprecated']
    if total_closed == 0:
        return ''

    parts = []
    if counts['completed']:
        parts.append(f"{counts['completed']} completed")
    if counts['deprecated']:
        parts.append(f"{counts['deprecated']} deprecated")
    summary = ' · '.join(parts)

    if dates:
        earliest = min(dates)
        span = (date.today() - earliest).days
        summary += f'  —  {span} days (since {earliest})'

    return summary


def truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[: n - 1] + '…'


def print_table(tasks: list[dict], state: str, page: int, per_page: int, total: int, summary: str = '') -> None:
    if not tasks:
        print(f'No {state} tasks.')
        return

    w_num = max(1, len(str(total)))
    w_created = 10
    w_status = max(6, max(len(t['status']) for t in tasks))
    w_model = min(30, max(5, max(len(t['model']) for t in tasks)))
    w_title = 55

    header = (
        f"{'#':<{w_num}}  "
        f"{'Created':<{w_created}}  "
        f"{'Title':<{w_title}}  "
        f"{'Status':<{w_status}}  "
        f"{'Model':<{w_model}}"
    )
    sep = '  '.join([
        '-' * w_num,
        '-' * w_created,
        '-' * w_title,
        '-' * w_status,
        '-' * w_model,
    ])

    total_pages = max(1, (total + per_page - 1) // per_page)
    start_idx = (page - 1) * per_page + 1

    print(f'\n  {state.upper()} tasks  —  page {page}/{total_pages}  ({total} total)\n')
    print(f'  {header}')
    print(f'  {sep}')
    for i, t in enumerate(tasks, start=start_idx):
        row = (
            f"{i:<{w_num}}  "
            f"{t['created']:<{w_created}}  "
            f"{truncate(t['title'], w_title):<{w_title}}  "
            f"{t['status']:<{w_status}}  "
            f"{truncate(t['model'], w_model):<{w_model}}"
        )
        print(f'  {row}')

    print()
    if total_pages > 1:
        print(f'  Page {page} of {total_pages} — use --page N to navigate.\n')
    if summary:
        print(f'  {summary}\n')


def main() -> None:
    parser = argparse.ArgumentParser(description='Show a summary table of task files')
    parser.add_argument(
        'state',
        nargs='?',
        default='pending',
        choices=['pending', 'completed', 'deprecated'],
        help='Task bucket to display (default: pending)',
    )
    parser.add_argument('--page', type=int, default=1, help='Page number (default: 1)')
    parser.add_argument('--per-page', type=int, default=20, dest='per_page',
                        help='Tasks per page (default: 20)')
    parser.add_argument('--cwd', default=None,
                        help='Project root directory (default: current directory)')
    args = parser.parse_args()

    root = Path(args.cwd) if args.cwd else Path.cwd()
    task_dir = root / 'tasks' / args.state

    if not task_dir.exists():
        print(f'Directory not found: {task_dir}', file=sys.stderr)
        sys.exit(1)

    files = sorted(task_dir.glob('*.md'))
    total = len(files)

    start = (args.page - 1) * args.per_page
    page_files = files[start: start + args.per_page]

    if not page_files and args.page > 1:
        total_pages = max(1, (total + args.per_page - 1) // args.per_page)
        print(f'Page {args.page} out of range (total pages: {total_pages}).', file=sys.stderr)
        sys.exit(1)

    tasks = [t for f in page_files if (t := parse_task(f))]
    summary = closed_summary(root)
    print_table(tasks, args.state, args.page, args.per_page, total, summary)


if __name__ == '__main__':
    main()
