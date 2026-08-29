from datetime import date
from pathlib import Path

from task import from_toml, to_toml
from workflow import TaskState, transition


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
    task = from_toml(task_path.read_text())
    transition(task.status, TaskState.hallucinated)

    task = task.model_copy(update={
        'status': TaskState.hallucinated,
        'hallucinating_agent': hallucinating_agent_handle,
        'hallucination_reporter': reporter,
        'hallucination_reason': reason,
        'results': {'hallucinated_solution': solution},
    })

    hallucinated_dir = cwd / 'tasks' / 'hallucinated'
    hallucinated_dir.mkdir(parents=True, exist_ok=True)
    dest = hallucinated_dir / task_path.name
    dest.write_text(to_toml(task))
    task_path.unlink()

    dev_log_path = cwd / 'development-log.md'
    if dev_log_path.exists():
        _append_dev_log(dev_log_path, task.title, reason)

    return dest
