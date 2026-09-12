from datetime import date, datetime, timezone
from pathlib import Path

from task import Revision, from_toml, next_section_number, to_toml
from workflow import TaskState, transition


def timestamps() -> tuple[str, str]:
    """UTC and local forms of one instant, so the two cannot disagree.

    at_utc is sortable and unambiguous; at_local is for a person, carrying the
    zone abbreviation rather than a numeric offset.
    """
    now = datetime.now(timezone.utc)
    return (
        now.isoformat(timespec='seconds'),
        now.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z'),
    )


def _append_dev_log(dev_log_path: Path, title: str, instructions: str) -> None:
    today = date.today().isoformat()
    entry = f'\n## {today} — {title} (revised)\n\n- {instructions}\n'
    with dev_log_path.open('a') as f:
        f.write(entry)


def record_revision(
    task_path: Path,
    agent: str,
    complexity: str,
    instructions: str,
    cwd: Path,
) -> Path:
    """Record a correction to a failed task and return it to pending.

    The task's own text is not edited — the correction lives in the revision.
    Only the latest revision is rendered to an executing model, so a second
    revision must restate anything from the first that still applies.
    """
    task = from_toml(task_path.read_text())
    transition(task.status, TaskState.pending)

    at_utc, at_local = timestamps()
    number = next_section_number(task)
    section = Revision(
        at_utc=at_utc,
        at_local=at_local,
        agent=agent,
        complexity=complexity,
        instructions=instructions,
    )

    task = task.model_copy(update={
        'status': TaskState.pending,
        'sections': {**task.sections, number: section},
        'latest_section': number,
    })
    # The file does not move — it is already in tasks/pending and stays there.
    task_path.write_text(to_toml(task))

    dev_log_path = cwd / 'development-log.md'
    if dev_log_path.exists():
        _append_dev_log(dev_log_path, task.title, instructions)

    return task_path
