#!/usr/bin/env python3
"""
hooks.py — context that agent harnesses add so the model can read track-tasks
notations (`^task:20260927091033`, see notation.py).

Invoked via:
  main.py hook session-start [--format text|claude] [--cwd DIR]
  main.py hook prompt        [--format text|claude] [--cwd DIR]   (prompt on stdin)

session-start prints the notation legend, once, when the project has a tasks/
directory. prompt prints the expanded forms of any notations in the prompt,
and nothing otherwise, so unrelated prompts add nothing to the context.

--format claude reads Claude Code's hook JSON on stdin (prompt and cwd) and
writes {"hookSpecificOutput": {...additionalContext}}; --format text reads and
writes plain text (pi's extension, manual testing).

Hooks run on every prompt, so they only read local TOML, and never fail
loudly: any error goes to stderr and the hook exits 0 with no output, leaving
the prompt untouched.
"""

import json
import os
import sys
from pathlib import Path

import notation

CLAUDE_EVENT_NAMES = {'session-start': 'SessionStart', 'prompt': 'UserPromptSubmit'}


def read_input(stdin_text: str, fmt: str) -> tuple[str, str]:
    """(prompt, cwd from the harness or '') from the hook's stdin."""
    if fmt == 'claude':
        data = json.loads(stdin_text or '{}')
        return data.get('prompt', ''), data.get('cwd', '')
    return stdin_text, ''


def format_output(text: str, event: str, fmt: str) -> str:
    """Wrap text for the harness; '' stays ''."""
    if not text:
        return ''
    if fmt == 'claude':
        return json.dumps({
            'hookSpecificOutput': {
                'hookEventName': CLAUDE_EVENT_NAMES[event],
                'additionalContext': text,
            }
        })
    return text


def run(event: str, fmt: str, stdin_text: str, cwd: str | None) -> str:
    """The hook's output for one event."""
    prompt, harness_cwd = read_input(stdin_text, fmt)
    root = Path(cwd or harness_cwd or os.getcwd())
    if event == 'session-start':
        text = notation.legend() if (root / 'tasks').is_dir() else ''
    else:
        text = notation.expand_prompt(prompt, root)
    return format_output(text, event, fmt)


def main(event: str, fmt: str, cwd: str | None) -> None:
    """Entry point for `main.py hook`; never raises and never exits non-zero."""
    try:
        # Plain-text session-start has nothing on stdin; don't wait for it.
        stdin_text = sys.stdin.read() if event == 'prompt' or fmt == 'claude' else ''
        output = run(event, fmt, stdin_text, cwd)
    except Exception as error:  # a hook must never block the user's prompt
        print(f'track-tasks hook {event}: {error}', file=sys.stderr)
        return
    if output:
        print(output)
