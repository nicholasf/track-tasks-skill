#!/usr/bin/env python3
"""
notation.py — skill notations for track-tasks, e.g. `^task:20260927091033`.

A notation is a short reference typed into a prompt. This skill resolves it
into an expanded form, the text the notation stands for, which the prompt hook
adds to the context after the prompt:

  ^task     the notation key, declared in SKILL.md front matter (metadata.notation-key)
  2026...   the payload, URL-encoded (`+` for a space), resolved by this skill

  <skill-notation skill="track-tasks">
    <notation>^task:20260927091033</notation>
    <expanded>Task 20260927091033: Add the failed state ...</expanded>
  </skill-notation>

A notation that cannot be resolved gets <error> in place of <expanded>, so the
model never guesses. The block format is the same as the topology skill's (see
the skill notation plan in the notes repo).

Payloads this skill understands, looked up in the project's tasks/ directory:
  (none)            ^task                            pending and in-progress tasks
  short code        ^task:20260927091033             that task
  slug              ^task:add-the-failed-state       that task (file name without the timestamp)
  bucket            ^task:completed                  the newest 20 tasks in that bucket
  bucket:count      ^task:completed:33               the newest 33
Anything else gives <error> with suggestions.
"""

import difflib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote_plus, unquote_plus
from xml.sax.saxutils import escape, quoteattr

from task import Failure, Task, from_toml, latest_revision

SKILL_MD = Path(__file__).resolve().parents[1] / 'SKILL.md'
DEFAULT_KEY = '^task'
DEFAULT_SKILL_NAME = 'track-tasks'
BUCKETS = ('pending', 'completed', 'deprecated', 'hallucinated')
TRAILING_PUNCTUATION = '.,;:!?)\'"'
TIMESTAMP_PREFIX = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}-')
DEFAULT_LISTED = 20


@dataclass
class TaskFile:
    """A parsed task together with where it lives."""
    task: Task
    path: Path
    bucket: str

    @property
    def slug(self) -> str:
        """The file name without its timestamp prefix and extension."""
        return TIMESTAMP_PREFIX.sub('', self.path.stem)

    @property
    def handle(self) -> str:
        """The handle that names this task: its short code, or its slug for older tasks."""
        return self.task.short_code or self.slug


# ── Front matter ─────────────────────────────────────────────────────────────

def front_matter_value(pattern: str, default: str, skill_md: Path = SKILL_MD) -> str:
    """First capture of `pattern` in SKILL.md front matter, or `default` (no YAML dependency)."""
    try:
        text = skill_md.read_text()
    except OSError:
        return default
    front = re.match(r'---\n(.*?)\n---', text, re.S)
    found = front and re.search(pattern, front.group(1), re.M)
    return found.group(1) if found else default


def read_notation_key(skill_md: Path = SKILL_MD) -> str:
    """metadata.notation-key from SKILL.md front matter."""
    return front_matter_value(r'^\s+notation-key:\s*["\']?([^\s"\']+)', DEFAULT_KEY, skill_md)


def read_skill_name(skill_md: Path = SKILL_MD) -> str:
    """name from SKILL.md front matter; shown as the skill attribute on each block."""
    return front_matter_value(r'^name:\s*["\']?([^\s"\']+)', DEFAULT_SKILL_NAME, skill_md)


def legend(key: str | None = None) -> str:
    """The session-start line that tells the model how to read this skill's notations."""
    key = key or read_notation_key()
    return (
        f'Notation: {key} or {key}:<short code|slug|{"|".join(BUCKETS)}[:count]> in the user\'s message '
        'refers to a track-tasks task file and is followed by <skill-notation> blocks, '
        'each pairing the notation with its expanded form.'
    )


# ── Finding notations ────────────────────────────────────────────────────────

def find_notations(prompt: str, key: str) -> list[tuple[str, str]]:
    """(notation as typed, decoded payload) for each notation, in order, without duplicates.

    A notation starts at the beginning of the prompt or after whitespace, and
    the key must not run on into a word (`^tasks` is not one). Trailing
    sentence punctuation (`is ^task:x done?`) is not part of the notation.
    """
    pattern = re.compile(r'(?<!\S)' + re.escape(key) + r'(?::(\S*))?(?![\w-])')
    found: list[tuple[str, str]] = []
    for match in pattern.finditer(prompt):
        raw = (match.group(1) or '').rstrip(TRAILING_PUNCTUATION)
        notation = f'{key}:{raw}' if raw else key
        if notation not in (n for n, _ in found):
            found.append((notation, unquote_plus(raw)))
    return found


# ── Loading tasks ────────────────────────────────────────────────────────────

def load_tasks(root: Path) -> list[TaskFile]:
    """Every parseable task under root/tasks/, oldest first within each bucket."""
    tasks: list[TaskFile] = []
    for bucket in BUCKETS:
        for path in sorted((root / 'tasks' / bucket).glob('*.toml')):
            try:
                task = from_toml(path.read_text())
            except Exception:
                # Same policy as show: one malformed file must not break the rest.
                continue
            tasks.append(TaskFile(task, path, bucket))
    return tasks


# ── Resolving payloads ───────────────────────────────────────────────────────

def relative(path: Path, root: Path) -> str:
    """path relative to root when it is inside it, else the full path."""
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def one_line(item: TaskFile) -> str:
    """A single summary line for a task in a listing."""
    return f'{item.handle}  [{item.task.status}]  {item.task.title}'


def describe_task(item: TaskFile, root: Path) -> str:
    """The expanded form of one task: what it is, where it is and where it stands."""
    task = item.task
    lines = [
        f'Task {item.handle}: {task.title}',
        f'Status: {task.status}. File: {relative(item.path, root)}',
    ]
    if task.short_code:
        lines.append(f'Short code: {task.short_code}. Slug: {item.slug}')
    if task.branch:
        lines.append(f'Branch: {task.branch}')
    if task.worktree_path:
        lines.append(f'Worktree: {task.worktree_path}')
    lines.append(f'Execution mode: {task.execution_mode}. Agent: {task.agent}. Model: {task.model}')
    lines.append(f'Goal: {task.goal}')
    if task.done_when:
        lines.append('Done when: ' + '; '.join(task.done_when))
    if task.sub_tasks:
        done = sum(1 for s in task.sub_tasks if s.done)
        subs = ', '.join(f'{s.slug or s.path} ({"done" if s.done else "not done"})' for s in task.sub_tasks)
        lines.append(f'Programme: {done}/{len(task.sub_tasks)} sub-tasks done: {subs}')
    # Only the count: failure outcomes and logs stay out of model-facing text,
    # as in render(). They are in the task file for anyone who needs them.
    failures = sum(1 for s in task.sections.values() if isinstance(s, Failure))
    if failures:
        lines.append(f'Failed attempts: {failures} (details in the task file)')
    revision = latest_revision(task)
    if revision is not None and revision.instructions:
        lines.append(f'Latest revision: {revision.instructions}')
    if task.results.get('summary'):
        lines.append(f'Result: {task.results["summary"]}')
    if task.deprecated_by:
        lines.append(f'Deprecated by: {task.deprecated_by}')
    return '\n'.join(lines)


def describe_listing(heading: str, items: list[TaskFile], limit: int = DEFAULT_LISTED) -> str:
    """A heading followed by one line per task, the newest `limit` of them."""
    if not items:
        return f'{heading}: none.'
    shown = items[-limit:]
    lines = [f'{heading} ({len(items)}):'] + [f'  {one_line(i)}' for i in shown]
    if len(items) > len(shown):
        lines.append(f'  … {len(items) - len(shown)} older not shown.')
    return '\n'.join(lines)


def all_handles(tasks: list[TaskFile]) -> list[str]:
    """Every payload this skill resolves, for suggestions."""
    handles = set(BUCKETS)
    for item in tasks:
        handles |= {item.slug, item.task.short_code}
    return sorted(handles - {''})


def suggest(wanted: str, handles: list[str], n: int = 3) -> list[str]:
    """Up to n handles close to wanted.

    Slugs are long, so a partial one (`add-failed`) scores too low for difflib
    alone; handles containing every word of wanted, in order, come first.
    """
    words = [w for w in re.split(r'[-\s]+', wanted) if w]
    in_order = re.compile('.*'.join(re.escape(w) for w in words)) if words else None
    containing = [h for h in handles if in_order and in_order.search(h.lower())]
    close = difflib.get_close_matches(wanted, handles, n=n, cutoff=0.5)
    return list(dict.fromkeys(containing + close))[:n]


def expand(payload: str, root: Path, tasks: list[TaskFile]) -> tuple[str, str, str]:
    """Resolve a payload. Returns (tag, kind, text); tag is 'expanded' or 'error'."""
    if not (root / 'tasks').is_dir():
        return 'error', 'none', f'No tasks/ directory in {root}; this project does not use track-tasks yet.'

    if not payload:
        active = [t for t in tasks if t.bucket == 'pending']
        return 'expanded', 'summary', describe_listing('Pending and in-progress tasks', active)

    wanted = payload.lower()
    bucket, _, count = wanted.partition(':')
    if bucket in BUCKETS:
        if count and not (count.isdigit() and int(count) > 0):
            return 'error', 'count', (f"'{count}' is not a count. Use {bucket}:<n> with n a whole number "
                                      f"above 0, e.g. {bucket}:{DEFAULT_LISTED}.")
        items = [t for t in tasks if t.bucket == bucket]
        limit = int(count) if count else DEFAULT_LISTED
        return 'expanded', 'bucket', describe_listing(f'{bucket.capitalize()} tasks', items, limit)

    matches = [t for t in tasks if wanted in {t.task.short_code.lower(), t.slug.lower()} - {''}]
    if matches:
        return 'expanded', 'task', '\n\n'.join(describe_task(t, root) for t in matches)

    text = f"Unknown handle '{payload}' in tasks/."
    suggestions = suggest(wanted, all_handles(tasks))
    if suggestions:
        text += ' Did you mean: ' + ', '.join(suggestions) + '?'
    return 'error', 'unknown', text


# ── Expanded form ────────────────────────────────────────────────────────────

def build_expanded_form(notation: str, tag: str, text: str, skill: str) -> str:
    """One <skill-notation> block; tag is 'expanded' or 'error'."""
    return (
        f'<skill-notation skill={quoteattr(skill)}>\n'
        f'  <notation>{escape(notation)}</notation>\n'
        f'  <{tag}>\n'
        + '\n'.join(f'    {line}' if line else '' for line in escape(text).splitlines())
        + f'\n  </{tag}>\n'
        '</skill-notation>'
    )


def expand_prompt(prompt: str, root: Path, key: str | None = None) -> str:
    """Expanded forms for every notation in the prompt, or '' when there are none."""
    key = key or read_notation_key()
    notations = find_notations(prompt, key)
    if not notations:
        return ''
    skill = read_skill_name()
    tasks = load_tasks(root)
    forms = []
    for notation, payload in notations:
        tag, _kind, text = expand(payload, root, tasks)
        forms.append(build_expanded_form(notation, tag, text, skill))
    return '\n'.join(forms)


# ── Completion (pi autocomplete) ─────────────────────────────────────────────

def encode_payload(handle: str) -> str:
    """URL-encode a handle for a notation; `+` for spaces."""
    return quote_plus(handle)


def completion_items(tasks: list[TaskFile]) -> list[dict]:
    """Handles this skill can resolve, each as {value, description}, newest task first."""
    items: list[dict] = []
    seen: set[str] = set()

    def add(handle: str, description: str) -> None:
        value = encode_payload(handle)
        if handle and value not in seen:
            seen.add(value)
            items.append({'value': value, 'description': description})

    for bucket in BUCKETS:
        add(bucket, f'list {bucket} tasks')
    for item in sorted(tasks, key=lambda t: t.path.name, reverse=True):
        description = f'{item.bucket}: {item.task.title}'
        add(item.task.short_code, description)
        add(item.slug, description)
    return items


def build_completion(root: Path) -> dict:
    """The completion payload pi loads once per session."""
    return {
        'key': read_notation_key(),
        'skill': read_skill_name(),
        'description': 'task files in this project',
        'handles': completion_items(load_tasks(root)),
    }


def main(argv: list[str], root: Path) -> None:
    """Entry point for `main.py notation complete`."""
    if argv != ['complete']:
        print('usage: main.py notation complete [--cwd DIR]', file=sys.stderr)
        sys.exit(1)
    print(json.dumps(build_completion(root)))
