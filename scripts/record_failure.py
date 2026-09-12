from datetime import date
from pathlib import Path

from record_revision import timestamps
from task import Failure, from_toml, next_section_number, to_toml
from workflow import TaskState, transition


def _append_dev_log(dev_log_path: Path, title: str, outcome: str) -> None:
    today = date.today().isoformat()
    entry = f'\n## {today} — {title} (failed)\n\n- {outcome}\n'
    with dev_log_path.open('a') as f:
        f.write(entry)


def record_failure(
    task_path: Path,
    agent: str,
    model: str,
    complexity: str,
    outcome: str,
    log: str,
    cwd: Path,
) -> Path:
    task = from_toml(task_path.read_text())
    transition(task.status, TaskState.failed)

    at_utc, at_local = timestamps()
    section = Failure(
        at_utc=at_utc,
        at_local=at_local,
        agent=agent,
        model=model,
        complexity=complexity,
        outcome=outcome,
        log=log,
    )
    number = next_section_number(task)
    sections = {**task.sections, number: section}

    task = task.model_copy(update={
        'status': TaskState.failed,
        'sections': sections,
        'latest_section': number,
    })
    # Unlike deprecate and complete, the file does not move: a failed task is
    # still wanted, so it stays in tasks/pending.
    task_path.write_text(to_toml(task))

    dev_log_path = cwd / 'development-log.md'
    if dev_log_path.exists():
        _append_dev_log(dev_log_path, task.title, outcome)

    return task_path
