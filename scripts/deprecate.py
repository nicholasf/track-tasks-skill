from datetime import date
from pathlib import Path

from task import from_toml, to_toml
from workflow import TaskState, transition


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
    task = from_toml(task_path.read_text())
    transition(task.status, TaskState.deprecated)

    update = {'status': TaskState.deprecated}
    if deprecated_by:
        update['deprecated_by'] = deprecated_by
    task = task.model_copy(update=update)

    deprecated_dir = cwd / 'tasks' / 'deprecated'
    deprecated_dir.mkdir(parents=True, exist_ok=True)
    dest = deprecated_dir / task_path.name
    dest.write_text(to_toml(task))
    task_path.unlink()

    dev_log_path = cwd / 'development-log.md'
    if dev_log_path.exists():
        _append_dev_log(dev_log_path, task.title, reason)

    return dest
