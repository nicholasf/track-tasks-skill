from datetime import date, datetime, timezone
from pathlib import Path

from task import Section, from_toml, to_toml
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

    now = datetime.now(timezone.utc)
    section = Section(
        type='failure',
        at_utc=now.isoformat(timespec='seconds'),
        # Readable local form with the zone abbreviation — at_utc already
        # covers the sortable, unambiguous case, so this one is for a person.
        at_local=now.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'),
        agent=agent,
        model=model,
        complexity=complexity,
        outcome=outcome,
        log=log,
    )
    next_number = max((int(key) for key in task.sections), default=0) + 1
    sections = {**task.sections, str(next_number): section}

    task = task.model_copy(update={'status': TaskState.failed, 'sections': sections})
    # Unlike deprecate and complete, the file does not move: a failed task is
    # still wanted, so it stays in tasks/pending.
    task_path.write_text(to_toml(task))

    dev_log_path = cwd / 'development-log.md'
    if dev_log_path.exists():
        _append_dev_log(dev_log_path, task.title, outcome)

    return task_path
