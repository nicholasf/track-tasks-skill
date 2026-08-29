from datetime import date
from pathlib import Path

from task import from_toml, to_toml
from workflow import TaskState, transition


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
    task = from_toml(task_path.read_text())
    transition(task.status, TaskState.completed)

    task = task.model_copy(update={
        'status': TaskState.completed,
        'results': {'tests': tests, 'files_changed': files_changed, 'summary': summary},
    })

    completed_dir = cwd / 'tasks' / 'completed'
    completed_dir.mkdir(parents=True, exist_ok=True)
    dest = completed_dir / task_path.name
    dest.write_text(to_toml(task))
    task_path.unlink()

    dev_log_path = cwd / 'development-log.md'
    if dev_log_path.exists():
        _append_dev_log(dev_log_path, task.title, summary)

    return dest
