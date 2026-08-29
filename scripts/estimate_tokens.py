"""
estimate_tokens.py — estimate token usage for a task before delegating to a remote agent.

Algorithm:
  estimated_total = spec_tokens + file_tokens + reasoning_buffer

  spec_tokens     — tokenize the task file itself
  file_tokens     — tokenize each file listed under "## Files to read before starting"
  reasoning_buffer — from agent_state in topology.toml for the target agent handle

Complexity levels:
  L1  < 25K tokens  — fits comfortably in a 65K context window
  L2  25K–40K       — safe but snug; watch for overflow
  L3  > 40K         — must split before sending

The Pre-flight section is appended to the task file before delegation.

Sources (all arrays in topology.toml, written by topology-skill):
  context_window   — model_state
  reasoning_buffer — agent_state
  tok/s            — benchmarks
"""

import json
import os
import tomllib
import urllib.request
from pathlib import Path

from task import from_toml, to_toml

DEFAULT_REASONING_BUFFER = 12_000
# Fallback thresholds used when context_window is not available from topology.
L1_THRESHOLD = 25_000
L2_THRESHOLD = 40_000
# Fractions of context_window used when it is available.
L1_FRACTION = 0.40
L2_FRACTION = 0.60


def get_topology_path() -> str:
    topologies_home = os.environ.get('TOPOLOGIES_HOME', os.path.expanduser('~/.agents/skills'))
    return os.path.join(topologies_home, 'topology.toml')


# ── Topology readers ──────────────────────────────────────────────────────────

def _read_topology_array(topology_path: str, key: str) -> list[dict]:
    try:
        with open(topology_path, 'rb') as f:
            return tomllib.load(f).get(key, [])
    except FileNotFoundError:
        return []


def read_topology_context_window(topology_path: str, hostname: str, backend: str) -> int | None:
    """Read context_window from model_state for the given (hostname, backend) row."""
    for row in _read_topology_array(topology_path, 'model_state'):
        if row.get('hostname') == hostname and row.get('backend') == backend:
            return row.get('context_window')
    return None


def read_topology_reasoning_buffer(topology_path: str, hostname: str, agent_name: str) -> int:
    """Read reasoning_buffer from agent_state; fall back to DEFAULT_REASONING_BUFFER."""
    for row in _read_topology_array(topology_path, 'agent_state'):
        if row.get('hostname') == hostname and row.get('agent') == agent_name:
            return row.get('reasoning_buffer', DEFAULT_REASONING_BUFFER)
    return DEFAULT_REASONING_BUFFER


def read_topology_tok_s(topology_path: str, hostname: str, model: str) -> float | None:
    """Read tok/s from benchmarks for the given (hostname, model) row."""
    for row in _read_topology_array(topology_path, 'benchmarks'):
        if row.get('hostname') == hostname and row.get('model') == model:
            return row.get('tok_s')
    return None


# ── Tokenisation ──────────────────────────────────────────────────────────────

def tokenize_llama(host: str, text: str, port: int = 9337) -> int | None:
    """POST to llama-server /tokenize; return token count."""
    try:
        body = json.dumps({'content': text}).encode()
        req = urllib.request.Request(
            f'http://{host}:{port}/tokenize',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        tokens = data.get('tokens', [])
        return len(tokens)
    except Exception:
        return None


def tokenize_ollama(host: str, model: str, text: str, port: int = 11434) -> int | None:
    """POST to Ollama /api/tokenize; return token count."""
    try:
        body = json.dumps({'model': model, 'prompt': text}).encode()
        req = urllib.request.Request(
            f'http://{host}:{port}/api/tokenize',
            data=body,
            headers={'Content-Type': 'application/json'},
            method='POST',
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read())
        tokens = data.get('tokens', [])
        return len(tokens)
    except Exception:
        return None


# ── Complexity ────────────────────────────────────────────────────────────────

def complexity_level(estimated_total: int, context_window: int | None = None) -> str:
    if context_window:
        l1 = int(context_window * L1_FRACTION)
        l2 = int(context_window * L2_FRACTION)
    else:
        l1 = L1_THRESHOLD
        l2 = L2_THRESHOLD
    if estimated_total < l1:
        return 'L1'
    if estimated_total <= l2:
        return 'L2'
    return 'L3'


def complexity_note(level: str) -> str:
    return {
        'L1': 'fits comfortably — well within context window',
        'L2': 'safe but snug — watch for overflow',
        'L3': 'must split before sending',
    }[level]


def difficulty_rating(level: str) -> str:
    return {'L1': '⏳', 'L2': '⏳⏳', 'L3': '⏳⏳⏳'}[level]


# ── Pre-flight block ──────────────────────────────────────────────────────────

def build_token_estimate_section(
    spec_tokens: int,
    file_token_counts: dict[str, int],
    reasoning_buffer: int,
    context_window: int | None,
    tok_s: float | None,
    source: str = 'local',
) -> str:
    file_total = sum(file_token_counts.values())
    estimated_total = spec_tokens + file_total + reasoning_buffer
    level = complexity_level(estimated_total, context_window)
    note = complexity_note(level)
    rating = difficulty_rating(level)

    time_str = ''
    if tok_s and tok_s > 0:
        secs = estimated_total / tok_s
        time_str = f' (~{secs:.0f}s)'

    lines = [f'## Pre-flight {rating} {level}{time_str} ({source})', '']
    lines.append(f'- Spec: {spec_tokens:,} tokens')

    if file_token_counts:
        detail = ', '.join(f'{Path(p).name} ({n:,})' for p, n in file_token_counts.items())
        lines.append(f'- Files: {detail} → {file_total:,} total')
    else:
        lines.append('- Files: (none listed)')

    lines.append(f'- Reasoning buffer: {reasoning_buffer:,} (estimated)')
    lines.append(f'- Estimated total: ~{estimated_total:,} tokens')
    lines.append(f'- Complexity: {level} — {note}')

    if context_window:
        fits = estimated_total < (context_window - reasoning_buffer)
        lines.append(f'- Context window: {context_window:,} — {"fits" if fits else "OVERFLOW RISK"}')

    if tok_s and tok_s > 0:
        lines.append(f'- Time estimate: ~{secs:.0f}s at {tok_s:.0f} t/s')

    lines.append('')
    return '\n'.join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_token_estimate(
    task_path: str,
    hostname: str,
    backend: str,
    agent_name: str,
    model: str,
    topology_path: str | None = None,
    cwd: str | None = None,
) -> str:
    """Compute and return the Pre-flight section text (does not write to disk)."""
    if topology_path is None:
        topology_path = get_topology_path()

    with open(task_path) as f:
        task = from_toml(f.read())

    # Tokenize without any existing preflight, so retokenising doesn't count a
    # stale estimate as part of the spec.
    task_for_tokens = to_toml(task.model_copy(update={'preflight': ''}))

    if backend == 'ollama':
        spec_tokens = tokenize_ollama(hostname, model, task_for_tokens)
    else:
        spec_tokens = tokenize_llama(hostname, task_for_tokens)

    if spec_tokens is None:
        raise RuntimeError(f'Tokenisation failed: could not reach {backend} on {hostname}')

    file_token_counts: dict[str, int] = {}
    base = cwd or os.path.dirname(os.path.abspath(task_path))
    for rel_path in task.files_to_read:
        abs_path = os.path.join(base, rel_path) if not os.path.isabs(rel_path) else rel_path
        try:
            with open(abs_path) as f:
                content = f.read()
        except FileNotFoundError:
            continue
        if backend == 'ollama':
            count = tokenize_ollama(hostname, model, content)
        else:
            count = tokenize_llama(hostname, content)
        if count is not None:
            file_token_counts[rel_path] = count

    reasoning_buffer = read_topology_reasoning_buffer(topology_path, hostname, agent_name)
    context_window = read_topology_context_window(topology_path, hostname, backend)
    tok_s = read_topology_tok_s(topology_path, hostname, model)

    return build_token_estimate_section(
        spec_tokens=spec_tokens,
        file_token_counts=file_token_counts,
        reasoning_buffer=reasoning_buffer,
        context_window=context_window,
        tok_s=tok_s,
        source='remote',
    )


def append_token_estimate(task_path: str, preflight_text: str) -> None:
    """Set the task's preflight field and write it back to disk."""
    with open(task_path) as f:
        task = from_toml(f.read())

    task = task.model_copy(update={'preflight': preflight_text})

    with open(task_path, 'w') as f:
        f.write(to_toml(task))


