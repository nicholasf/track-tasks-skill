#!/usr/bin/env python3
"""
preflight.py — estimate token usage for a task before delegating to a remote agent.

Algorithm:
  estimated_total = spec_tokens + file_tokens + reasoning_buffer

  spec_tokens     — tokenize the task file itself
  file_tokens     — tokenize each file listed under "## Files to read before starting"
  reasoning_buffer — from Agent State in topology.md for the target agent handle

Complexity levels:
  L1  < 25K tokens  — fits comfortably in a 65K context window
  L2  25K–40K       — safe but snug; watch for overflow
  L3  > 40K         — must split before sending

The Pre-flight section is appended to the task file before delegation.

Sources:
  context_window   — ## Model State in topology.md (written by load-topology-skill)
  reasoning_buffer — ## Agent State in topology.md (written by ask-remote-agent-skill)
  tok/s            — ## LLM Benchmarks in topology.md (written by load-topology-skill)
"""

import json
import os
import re
import sys
import urllib.request
from pathlib import Path

DEFAULT_REASONING_BUFFER = 12_000
L1_THRESHOLD = 25_000
L2_THRESHOLD = 40_000


def get_topology_path() -> str:
    skills_home = os.environ.get('SKILLS_HOME', os.path.expanduser('~/.agents/skills'))
    return os.environ.get('TOPOLOGY_PATH', os.path.join(skills_home, 'topology.md'))


# ── Topology readers ──────────────────────────────────────────────────────────

def _parse_section_table(lines: list[str], header: str) -> list[dict]:
    """Parse the first markdown table found after `header` in lines."""
    in_section = False
    headers: list[str] | None = None
    rows: list[dict] = []
    for line in lines:
        if line.strip() == header:
            in_section = True
            continue
        if in_section and line.startswith('## ') and line.strip() != header:
            break
        if not in_section:
            continue
        if line.startswith('| ') and headers is None and '---' not in line:
            headers = [h.strip() for h in line.split('|')[1:-1]]
        elif headers and line.startswith('|') and '---' not in line:
            values = [v.strip() for v in line.split('|')[1:-1]]
            rows.append(dict(zip(headers, values[:len(headers)])))
    return rows


def read_topology_context_window(topology_path: str, hostname: str, backend: str) -> int | None:
    """Read context_window from ## Model State for the given (hostname, backend) row."""
    try:
        with open(topology_path) as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return None
    rows = _parse_section_table(lines, '## Model State')
    for row in rows:
        if row.get('hostname') == hostname and row.get('backend') == backend:
            val = row.get('context_window', '—')
            if val and val != '—':
                try:
                    return int(val)
                except ValueError:
                    pass
    return None


def read_topology_reasoning_buffer(topology_path: str, hostname: str, agent_name: str) -> int:
    """Read reasoning_buffer from ## Agent State; fall back to DEFAULT_REASONING_BUFFER."""
    try:
        with open(topology_path) as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return DEFAULT_REASONING_BUFFER
    rows = _parse_section_table(lines, '## Agent State')
    for row in rows:
        if row.get('hostname') == hostname and row.get('agent') == agent_name:
            val = row.get('reasoning_buffer', '—')
            if val and val != '—':
                try:
                    return int(val)
                except ValueError:
                    pass
    return DEFAULT_REASONING_BUFFER


def read_topology_tok_s(topology_path: str, hostname: str, model: str) -> float | None:
    """Read tok/s from ## LLM Benchmarks for the given (hostname, model) row."""
    try:
        with open(topology_path) as f:
            lines = f.read().splitlines()
    except FileNotFoundError:
        return None
    rows = _parse_section_table(lines, '## LLM Benchmarks')
    for row in rows:
        if row.get('hostname') == hostname and row.get('model') == model:
            val = row.get('tok_s', '—')
            if val and val != '—':
                try:
                    return float(val)
                except ValueError:
                    pass
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


# ── Task file parsing ─────────────────────────────────────────────────────────

def parse_model_field(task_text: str) -> str | None:
    """Extract the value of the **Model:** field from a task file."""
    m = re.search(r'^\*\*Model:\*\*\s*(.+)$', task_text, re.MULTILINE)
    return m.group(1).strip() if m else None


def parse_files_to_read(task_text: str) -> list[str]:
    """Extract file paths listed under '## Files to read before starting'."""
    m = re.search(
        r'^## Files to read before starting\s*\n(.*?)(?=^##|\Z)',
        task_text, re.MULTILINE | re.DOTALL,
    )
    if not m:
        return []
    block = m.group(1)
    paths = []
    for line in block.splitlines():
        line = line.strip().lstrip('-').strip()
        if line and not line.startswith('#'):
            paths.append(line)
    return paths


# ── Complexity ────────────────────────────────────────────────────────────────

def complexity_level(estimated_total: int) -> str:
    if estimated_total < L1_THRESHOLD:
        return 'L1'
    if estimated_total <= L2_THRESHOLD:
        return 'L2'
    return 'L3'


def complexity_note(level: str) -> str:
    return {
        'L1': 'fits comfortably in a 65K window',
        'L2': 'safe but snug — watch for overflow',
        'L3': 'must split before sending',
    }[level]


# ── Pre-flight block ──────────────────────────────────────────────────────────

def build_preflight_section(
    spec_tokens: int,
    file_token_counts: dict[str, int],
    reasoning_buffer: int,
    context_window: int | None,
    tok_s: float | None,
) -> str:
    file_total = sum(file_token_counts.values())
    estimated_total = spec_tokens + file_total + reasoning_buffer
    level = complexity_level(estimated_total)
    note = complexity_note(level)

    lines = ['## Pre-flight', '']
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
        secs = estimated_total / tok_s
        lines.append(f'- Time estimate: ~{secs:.0f}s at {tok_s:.0f} t/s')

    lines.append('')
    return '\n'.join(lines)


# ── Main ──────────────────────────────────────────────────────────────────────

def run_preflight(
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
        task_text = f.read()

    # Remove any existing Pre-flight section before retokenising
    task_for_tokens = re.sub(
        r'^## Pre-flight\s*\n.*?(?=^##|\Z)', '', task_text,
        flags=re.MULTILINE | re.DOTALL,
    ).strip()

    if backend == 'ollama':
        spec_tokens = tokenize_ollama(hostname, model, task_for_tokens)
    else:
        spec_tokens = tokenize_llama(hostname, task_for_tokens)

    if spec_tokens is None:
        raise RuntimeError(f'Tokenisation failed: could not reach {backend} on {hostname}')

    file_paths = parse_files_to_read(task_text)
    file_token_counts: dict[str, int] = {}
    base = cwd or os.path.dirname(os.path.abspath(task_path))
    for rel_path in file_paths:
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

    return build_preflight_section(
        spec_tokens=spec_tokens,
        file_token_counts=file_token_counts,
        reasoning_buffer=reasoning_buffer,
        context_window=context_window,
        tok_s=tok_s,
    )


def append_preflight(task_path: str, preflight_text: str) -> None:
    """Replace or append the ## Pre-flight section in the task file."""
    with open(task_path) as f:
        content = f.read()

    # Remove existing Pre-flight section
    content = re.sub(
        r'^## Pre-flight\s*\n.*?(?=^##|\Z)', '', content,
        flags=re.MULTILINE | re.DOTALL,
    ).rstrip()

    with open(task_path, 'w') as f:
        f.write(content + '\n\n' + preflight_text)


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description='Pre-flight token estimate for a task file')
    parser.add_argument('task', help='Path to the task file')
    parser.add_argument('--hostname', required=True, help='Inference node hostname')
    parser.add_argument('--backend', default='llama-server',
                        choices=['llama-server', 'ollama'],
                        help='Inference backend (default: llama-server)')
    parser.add_argument('--agent', default='hermes',
                        help='Agent name in topology Agent State (default: hermes)')
    parser.add_argument('--model', default='',
                        help='Model name (required for Ollama tokenisation)')
    parser.add_argument('--cwd', default=None,
                        help='Base directory for resolving relative file paths in the task')
    parser.add_argument('--write', action='store_true',
                        help='Append the Pre-flight section to the task file')
    args = parser.parse_args()

    preflight = run_preflight(
        task_path=args.task,
        hostname=args.hostname,
        backend=args.backend,
        agent_name=args.agent,
        model=args.model,
        cwd=args.cwd,
    )
    print(preflight)

    if args.write:
        append_preflight(args.task, preflight)
        print(f'Pre-flight section written to {args.task}', file=sys.stderr)


if __name__ == '__main__':
    main()
