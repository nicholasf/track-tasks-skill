import tomllib
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, Field

import toml_writer
from workflow import TaskState


class ExecutionMode(StrEnum):
    ask_llm = 'ask_llm'
    ask_agent = 'ask_agent'
    local = 'local'
    local_worktree = 'local_worktree'


class Section(BaseModel):
    """Base for the numbered records kept on a task.

    Holds only what is universal to every section type: what it is, and when.
    Everything about who acted and how big the work was belongs to the specific
    type, since those mean different things per type.

    Adding a third section type requires only a new subclass and an entry in
    AnySection — nothing else may branch on how many types exist.
    """
    type: str = ''
    at_utc: str = ''
    at_local: str = ''


class Failure(Section):
    """A run that was attempted and did not finish.

    Its outcome and log are never rendered, so they can be as detailed as
    needed — render is the model-facing view, and failure history accumulating
    in it would inflate the very context budget a retry needs.
    """
    type: Literal['failure'] = 'failure'
    agent: str = ''
    model: str = ''
    complexity: str = ''
    outcome: str = ''
    log: str = ''


class Revision(Section):
    """The correction made in response to a failure.

    Unlike a failure, a revision's instructions ARE rendered — they carry what
    the next attempt needs. Only the latest revision is rendered, so a second
    revision must restate anything from the first that still applies.
    """
    type: Literal['revision'] = 'revision'
    agent: str = ''
    complexity: str = ''
    instructions: str = ''


# Discriminated on `type` so from_toml restores the concrete subclass. Without
# the discriminator every section parses back as a bare Section and silently
# loses its subclass fields — a round-trip that loses data rather than failing.
AnySection = Annotated[Failure | Revision, Field(discriminator='type')]


class Task(BaseModel):
    title: str
    goal: str
    model: str
    agent: str
    status: TaskState = TaskState.pending
    created: str = ''
    background: str = ''
    changes: list[str] = []
    files_to_read: list[str] = []
    open_questions: list[str] = []
    recommended_approach: str = ''
    done_when: list[str] = []
    preflight: str = ''
    results: dict[str, str] = {}
    # Numbered records keyed by section number as a string, so they serialize
    # as [sections.1], [sections.2], ... A failure is never rendered; the
    # latest revision's instructions are.
    sections: dict[str, AnySection] = {}
    # The highest-numbered section, and the section a completed task was
    # completed under. Both for a person reading the file; neither is rendered.
    latest_section: str = ''
    completed_by_section: str = ''
    # Paths of the tasks this one coordinates. A programme is simply a task
    # with these populated; an ordinary task leaves them empty. Not rendered.
    sub_tasks: list[str] = []
    deprecated_by: str = ''
    hallucinating_agent: str = ''
    hallucination_reporter: str = ''
    hallucination_reason: str = ''
    execution_mode: ExecutionMode = ExecutionMode.local
    worktree_path: str = ''
    worktree_branch: str = ''


def to_toml(task: Task) -> str:
    """Serialize a Task to TOML — the on-disk storage format for task files."""
    return toml_writer.dumps(task)


def from_toml(text: str) -> Task:
    """Parse a Task from its TOML storage format."""
    return Task.model_validate(tomllib.loads(text))


def render(task: Task) -> str:
    parts: list[str] = [f'# {task.title}', '']
    parts += [
        f'**Created:** {task.created}',
        f'**Model:** {task.model}',
        f'**Agent:** `{task.agent}`',
        f'**Status:** {task.status}',
        '',
    ]

    _section(parts, 'Goal', task.goal)

    if task.background:
        _section(parts, 'Background', task.background)

    if task.changes:
        parts += ['## Changes', '']
        parts += [f'- {c}' for c in task.changes]
        parts.append('')

    if task.files_to_read:
        parts += ['## Files to read before starting', '']
        parts += [f'- {f}' for f in task.files_to_read]
        parts.append('')

    if task.open_questions:
        parts += ['## Open questions', '']
        parts += [f'- {q}' for q in task.open_questions]
        parts.append('')

    if task.recommended_approach:
        _section(parts, 'Recommended approach', task.recommended_approach)

    if task.done_when:
        parts += ['## Done when', '']
        parts += [f'- [ ] {d}' for d in task.done_when]
        parts.append('')

    _render_preflight(parts, task.preflight)

    parts += [
        '## Results',
        '<!-- Filled in by the executing model after completion -->',
        '**Tests:**',
        '**Files changed:**',
        '**Summary:**',
        '',
    ]

    revision = latest_revision(task)
    if revision is not None and revision.instructions:
        parts += ['## Revision', '', revision.instructions, '']

    return '\n'.join(parts)


def next_section_number(task: Task) -> str:
    """The key for the next section — one sequence shared across all types."""
    return str(max((int(k) for k in task.sections), default=0) + 1)


def latest_section_number(task: Task) -> str:
    """The highest-numbered section, or empty if there are none.

    Compared numerically, not lexically — otherwise '10' sorts before '9'.
    """
    numbers = [int(k) for k in task.sections]
    return str(max(numbers)) if numbers else ''


def latest_revision(task: Task) -> Revision | None:
    """The most recent Revision, or None.

    Filters by type rather than branching on how many types exist, so a third
    section type needs no change here.
    """
    revisions = [(int(k), v) for k, v in task.sections.items() if isinstance(v, Revision)]
    if not revisions:
        return None
    return max(revisions, key=lambda pair: pair[0])[1]


def _section(parts: list[str], heading: str, content: str) -> None:
    parts += [f'## {heading}', '', content, '']


def _render_preflight(parts: list[str], preflight: str) -> None:
    if preflight == 'unavailable-via-remote':
        parts += ['## Pre-flight', '', '*Preflight unavailable — remote tokenizer could not be reached.*', '']
    elif preflight == 'unavailable-via-local':
        parts += ['## Pre-flight', '', '*Preflight unavailable — local tokenizer failed.*', '']
    elif preflight:
        # The string from build_preflight_section already starts with '## Pre-flight ...'
        parts += [preflight, '']
    else:
        parts += ['## Pre-flight', '', '<!-- not yet computed -->', '']
