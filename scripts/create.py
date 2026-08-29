import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from task import Task, render, to_toml
from tokenizer import Tokenizer
from tokenizer_local import LocalTokenizer
from tokenizer_remote import RemoteTokenizer
from estimate_tokens import (
    build_token_estimate_section,
    get_topology_path,
    read_topology_context_window,
    read_topology_reasoning_buffer,
    read_topology_tok_s,
)


def select_tokenizer(local: bool, hostname: str, backend: str, model: str) -> tuple[Tokenizer, str]:
    if local or not hostname:
        return LocalTokenizer(), 'local'
    try:
        tokenizer = RemoteTokenizer(hostname=hostname, backend=backend, model=model)
        tokenizer.probe()
        return tokenizer, 'remote'
    except Exception as error:
        print(f'[create] remote tokenizer unavailable ({error}), using local tokenizer', file=sys.stderr)
        return LocalTokenizer(), 'local'


def _slug(title: str) -> str:
    lowered = title.lower()
    alphanumeric = re.sub(r'[^a-z0-9\s]', '', lowered)
    hyphenated = re.sub(r'\s+', '-', alphanumeric.strip())
    return hyphenated[:60]


def _compute_preflight(
    task: Task,
    tokenizer: Tokenizer,
    tokenizer_source: str,
    hostname: str,
    backend: str,
    agent_name: str,
    model: str,
    cwd: str,
) -> str:
    topology_path = get_topology_path()
    spec_tokens = tokenizer.count(render(task))

    file_token_counts: dict[str, int] = {}
    for rel_path in task.files_to_read:
        abs_path = rel_path if os.path.isabs(rel_path) else os.path.join(cwd, rel_path)
        try:
            content = Path(abs_path).read_text()
            file_token_counts[rel_path] = tokenizer.count(content)
        except FileNotFoundError:
            pass

    reasoning_buffer = (
        read_topology_reasoning_buffer(topology_path, hostname, agent_name)
        if hostname else 12_000
    )
    context_window = (
        read_topology_context_window(topology_path, hostname, backend)
        if hostname else None
    )
    tok_s = (
        read_topology_tok_s(topology_path, hostname, model)
        if hostname and model else None
    )

    return build_token_estimate_section(
        spec_tokens=spec_tokens,
        file_token_counts=file_token_counts,
        reasoning_buffer=reasoning_buffer,
        context_window=context_window,
        tok_s=tok_s,
        source=tokenizer_source,
    )


def create_task(
    task_fields: dict,
    tokenizer: Tokenizer,
    tokenizer_source: str,
    hostname: str,
    backend: str,
    agent_name: str,
    model: str,
    cwd: str,
) -> Path:
    created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    task = Task.model_validate({**task_fields, 'created': created})

    try:
        preflight_text = _compute_preflight(task, tokenizer, tokenizer_source, hostname, backend, agent_name, model, cwd)
        task = task.model_copy(update={'preflight': preflight_text})
    except Exception as error:
        print(f'[create] preflight failed: {error}', file=sys.stderr)
        task = task.model_copy(update={'preflight': f'unavailable-via-{tokenizer_source}'})

    timestamp = datetime.now().strftime('%Y-%m-%dT%H-%M-%S')
    slug = _slug(task.title)
    filename = f'{timestamp}-{slug}.toml'
    task_path = Path(cwd) / 'tasks' / 'pending' / filename
    task_path.parent.mkdir(parents=True, exist_ok=True)
    task_path.write_text(to_toml(task))
    return task_path


