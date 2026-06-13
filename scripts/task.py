from pydantic import BaseModel


class Task(BaseModel):
    title: str
    goal: str
    model: str
    agent: str
    status: str = 'planned'
    created: str = ''
    background: str = ''
    changes: list[str] = []
    files_to_read: list[str] = []
    open_questions: list[str] = []
    recommended_approach: str = ''
    done_when: list[str] = []
    preflight: str = ''


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
