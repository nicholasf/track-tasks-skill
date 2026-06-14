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


def _add_hallucination_metadata(
    content: str,
    hallucinating_agent_handle: str,
    reporter: str,
    reason: str,
) -> str:
    fields = ''
    if hallucinating_agent_handle:
        fields += f'**Hallucinating agent:** {hallucinating_agent_handle}\n'
    if reporter:
        fields += f'**Reported by:** {reporter}\n'
    if reason:
        fields += f'**Reason:** {reason}\n'
    if not fields:
        return content
    return re.sub(
        r'(\*\*Status:\*\*[^\n]*\n)',
        f'\\1{fields}',
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


def _append_dev_log(dev_log_path: Path, title: str, reason: str) -> None:
    today = date.today().isoformat()
    entry = f'\n## {today} — {title} (hallucinated)\n\n- {reason}\n'
    with dev_log_path.open('a') as f:
        f.write(entry)


def mark_as_hallucinated(
    task_path: Path,
    solution: str,
    hallucinating_agent_handle: str,
    reporter: str,
    reason: str,
    cwd: Path,
) -> Path:
    content = task_path.read_text()
    current = _read_status(content)
    transition(current, TaskState.hallucinated)

    title = _read_title(content)
    content = _set_status(content, TaskState.hallucinated)
    content = _add_hallucination_metadata(content, hallucinating_agent_handle, reporter, reason)
    content = _fill_results(content, solution)

    hallucinated_dir = cwd / 'tasks' / 'hallucinated'
    hallucinated_dir.mkdir(parents=True, exist_ok=True)
    dest = hallucinated_dir / task_path.name
    dest.write_text(content)
    task_path.unlink()

    dev_log_path = cwd / 'development-log.md'
    if dev_log_path.exists():
        _append_dev_log(dev_log_path, title, reason)

    return dest


