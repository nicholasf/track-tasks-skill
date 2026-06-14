import re
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


def _add_deprecated_by(content: str, deprecated_by: str) -> str:
    return re.sub(
        r'(\*\*Status:\*\*[^\n]*\n)',
        f'\\1**Deprecated by:** {deprecated_by}\n',
        content,
        count=1,
    )


def _append_dev_log(dev_log_path: Path, title: str, reason: str) -> None:
    today = date.today().isoformat()
    entry = f'\n## {today} — {title} (deprecated)\n\n- {reason}\n'
    with dev_log_path.open('a') as f:
        f.write(entry)


def deprecate_task(
    task_path: Path,
    reason: str,
    deprecated_by: str,
    cwd: Path,
) -> Path:
    content = task_path.read_text()
    current = _read_status(content)
    transition(current, TaskState.deprecated)

    title = _read_title(content)
    content = _set_status(content, TaskState.deprecated)
    if deprecated_by:
        content = _add_deprecated_by(content, deprecated_by)

    deprecated_dir = cwd / 'tasks' / 'deprecated'
    deprecated_dir.mkdir(parents=True, exist_ok=True)
    dest = deprecated_dir / task_path.name
    dest.write_text(content)
    task_path.unlink()

    dev_log_path = cwd / 'development-log.md'
    if dev_log_path.exists():
        _append_dev_log(dev_log_path, title, reason)

    return dest


