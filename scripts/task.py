import tomllib

from pydantic import BaseModel

from workflow import TaskState


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
    deprecated_by: str = ''
    hallucinating_agent: str = ''
    hallucination_reporter: str = ''
    hallucination_reason: str = ''


def _format_toml_value(value) -> str:
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return '[' + ', '.join(_format_toml_value(v) for v in value) + ']'
    text = str(value)
    if '\n' in text:
        # Literal multi-line string — no escape processing, so prose round-trips verbatim.
        return f"'''\n{text}'''"
    escaped = text.replace('\\', '\\\\').replace('"', '\\"')
    return f'"{escaped}"'


def to_toml(task: Task) -> str:
    """Serialize a Task to TOML — the on-disk storage format for task files."""
    data = task.model_dump(mode='json')
    results = data.pop('results')

    lines = [f'{key} = {_format_toml_value(value)}' for key, value in data.items()]

    if results:
        lines += ['', '[results]']
        lines += [f'{key} = {_format_toml_value(value)}' for key, value in results.items()]

    return '\n'.join(lines) + '\n'


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

    return '\n'.join(parts)


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
