#!/usr/bin/env python3
"""
hooks_install.py — install, remove and report the track-tasks notation hooks.

Invoked via:
  main.py hooks install   --target claude|pi [--scope user|project]
  main.py hooks uninstall --target claude|pi [--scope user|project]
  main.py hooks status    [--scope user|project]

claude  Adds SessionStart and UserPromptSubmit entries to settings.json that
        call `main.py hook ... --format claude`. Entries are recognised by
        HOOK_MARKER, so install is idempotent and uninstall removes only ours.
        The previous file is copied to settings.json.track-tasks-backup
        before every write.
pi      Symlinks hooks/pi/track-tasks.ts from this repo into pi's extensions
        directory, so pulling the repo updates the extension.
"""

import json
import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = '${SKILLS_HOME:-$HOME/.agents/skills}/track-tasks-skill'
CLI = f'"{SKILL_DIR}/.venv/bin/python3" "{SKILL_DIR}/scripts/main.py"'
HOOK_MARKER = 'track-tasks-skill/scripts/main.py" hook '
PI_EXTENSION_SOURCE = REPO_ROOT / 'hooks' / 'pi' / 'track-tasks.ts'
TARGETS = ('claude', 'pi')
SCOPES = ('user', 'project')


def target_path(target: str, scope: str, cwd: Path | None = None, home: Path | None = None) -> Path:
    """Where a target's hook configuration lives for a scope."""
    cwd = cwd or Path.cwd()
    home = home or Path.home()
    paths = {
        ('claude', 'user'): home / '.claude' / 'settings.json',
        ('claude', 'project'): cwd / '.claude' / 'settings.json',
        ('pi', 'user'): home / '.pi' / 'agent' / 'extensions' / 'track-tasks.ts',
        ('pi', 'project'): cwd / '.pi' / 'extensions' / 'track-tasks.ts',
    }
    return paths[(target, scope)]


# ── Claude Code ──────────────────────────────────────────────────────────────

def claude_hook_entries() -> dict[str, dict]:
    """The hook groups to add to Claude Code settings, by event."""
    return {
        'SessionStart': {'hooks': [{
            'type': 'command',
            'command': f'{CLI} hook session-start --format claude',
        }]},
        'UserPromptSubmit': {'hooks': [{
            'type': 'command',
            'command': f'{CLI} hook prompt --format claude',
            'timeout': 10,
        }]},
    }


def remove_claude_hooks(settings: dict) -> dict:
    """Drop every hook whose command contains HOOK_MARKER, pruning empty groups and events."""
    hooks = settings.get('hooks', {})
    for event in list(hooks):
        groups = []
        for group in hooks[event]:
            kept = [h for h in group.get('hooks', []) if HOOK_MARKER not in h.get('command', '')]
            if kept:
                groups.append({**group, 'hooks': kept})
        if groups:
            hooks[event] = groups
        else:
            del hooks[event]
    if 'hooks' in settings and not hooks:
        del settings['hooks']
    return settings


def add_claude_hooks(settings: dict) -> dict:
    """Settings with our hooks added exactly once."""
    settings = remove_claude_hooks(settings)
    hooks = settings.setdefault('hooks', {})
    for event, group in claude_hook_entries().items():
        hooks.setdefault(event, []).append(group)
    return settings


def claude_hooks_installed(settings: dict) -> bool:
    """Whether any of our hooks are in the settings."""
    return any(
        HOOK_MARKER in h.get('command', '')
        for groups in settings.get('hooks', {}).values()
        for group in groups
        for h in group.get('hooks', [])
    )


def read_settings(path: Path) -> dict:
    """Parsed settings.json, or {} when missing or empty."""
    if not path.exists():
        return {}
    text = path.read_text()
    return json.loads(text) if text.strip() else {}


def write_settings(path: Path, settings: dict) -> None:
    """Write settings.json, backing up the previous file first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(path.name + '.track-tasks-backup'))
    path.write_text(json.dumps(settings, indent=2) + '\n')


# ── Actions ──────────────────────────────────────────────────────────────────

def install(target: str, path: Path) -> str:
    """Install one target's hooks at path; returns a message for the user."""
    if target == 'claude':
        write_settings(path, add_claude_hooks(read_settings(path)))
        return f'claude: SessionStart and UserPromptSubmit hooks written to {path}'

    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        path.unlink()
    elif path.exists():
        raise FileExistsError(f'{path} exists and is not a symlink; remove it first')
    path.symlink_to(PI_EXTENSION_SOURCE)
    return f'pi: {path} -> {PI_EXTENSION_SOURCE} (run /reload in an open pi session)'


def uninstall(target: str, path: Path) -> str:
    """Remove one target's hooks from path; returns a message for the user."""
    if target == 'claude':
        if not path.exists():
            return f'claude: {path} does not exist'
        write_settings(path, remove_claude_hooks(read_settings(path)))
        return f'claude: track-tasks hooks removed from {path}'

    if path.is_symlink():
        path.unlink()
        return f'pi: removed {path}'
    return f'pi: no track-tasks symlink at {path}'


def is_installed(target: str, path: Path) -> bool:
    """Whether one target's hooks are installed at path."""
    if target == 'claude':
        return path.exists() and claude_hooks_installed(read_settings(path))
    return path.is_symlink()


def main(action: str, target: str | None, scope: str) -> None:
    """Entry point for `main.py hooks`."""
    if action == 'status':
        for t in (target,) if target else TARGETS:
            path = target_path(t, scope)
            state = 'installed' if is_installed(t, path) else 'not installed'
            print(f'{t:7} {state:14} {path}')
        return

    if target is None:
        print('[hooks] --target is required for install and uninstall', file=sys.stderr)
        sys.exit(1)
    path = target_path(target, scope)
    try:
        message = install(target, path) if action == 'install' else uninstall(target, path)
    except (OSError, json.JSONDecodeError) as error:
        print(f'[hooks] {target}: {error}', file=sys.stderr)
        sys.exit(1)
    print(message)
