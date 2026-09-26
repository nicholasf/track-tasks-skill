import os
import re
import pytest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from create import _slug, create_task
from task import from_toml


@pytest.fixture(autouse=True)
def suppress_visualisation(monkeypatch):
    monkeypatch.setenv('TOKENIZER_VISUALISE', '0')


class FakeTokenizer:
    source = 'local'

    def count(self, text: str) -> int:
        return 100


_MINIMAL_FIELDS = {
    'title': 'Add logging to gate',
    'goal': 'Gate logs all requests.',
    'model': 'qwen3-coder-30b on pond',
    'agent': 'pond-qwen-hermes',
}


# ── _slug ─────────────────────────────────────────────────────────────────────

def test_slug_lowercases():
    assert _slug('My Task') == 'my-task'


def test_slug_removes_special_characters():
    assert _slug('Add: foo/bar!') == 'add-foobar'


def test_slug_collapses_spaces():
    assert _slug('do  the  thing') == 'do-the-thing'


def test_slug_truncates_at_60():
    long_title = 'a ' * 40
    assert len(_slug(long_title)) <= 60


# ── create_task ───────────────────────────────────────────────────────────────

def test_create_task_writes_file(tmp_path):
    path = create_task(
        task_fields=_MINIMAL_FIELDS,
        tokenizer=FakeTokenizer(),
        tokenizer_source='local',
        hostname='',
        backend='llama-server',
        agent_name='hermes',
        model='',
        cwd=str(tmp_path),
    )
    assert path.exists()


def test_create_task_writes_to_pending(tmp_path):
    path = create_task(
        task_fields=_MINIMAL_FIELDS,
        tokenizer=FakeTokenizer(),
        tokenizer_source='local',
        hostname='',
        backend='llama-server',
        agent_name='hermes',
        model='',
        cwd=str(tmp_path),
    )
    assert 'tasks/pending' in str(path)


def test_create_task_filename_contains_slug(tmp_path):
    path = create_task(
        task_fields=_MINIMAL_FIELDS,
        tokenizer=FakeTokenizer(),
        tokenizer_source='local',
        hostname='',
        backend='llama-server',
        agent_name='hermes',
        model='',
        cwd=str(tmp_path),
    )
    assert 'add-logging-to-gate' in path.name


def test_create_task_file_contains_title(tmp_path):
    path = create_task(
        task_fields=_MINIMAL_FIELDS,
        tokenizer=FakeTokenizer(),
        tokenizer_source='local',
        hostname='',
        backend='llama-server',
        agent_name='hermes',
        model='',
        cwd=str(tmp_path),
    )
    assert 'title = "Add logging to gate"' in path.read_text()


def test_create_task_file_has_preflight_section(tmp_path):
    path = create_task(
        task_fields=_MINIMAL_FIELDS,
        tokenizer=FakeTokenizer(),
        tokenizer_source='local',
        hostname='',
        backend='llama-server',
        agent_name='hermes',
        model='',
        cwd=str(tmp_path),
    )
    content = path.read_text()
    assert '## Pre-flight' in content


def test_create_task_preflight_not_placeholder(tmp_path):
    path = create_task(
        task_fields=_MINIMAL_FIELDS,
        tokenizer=FakeTokenizer(),
        tokenizer_source='local',
        hostname='',
        backend='llama-server',
        agent_name='hermes',
        model='',
        cwd=str(tmp_path),
    )
    content = path.read_text()
    assert 'not yet computed' not in content


def test_create_task_unavailable_label_on_tokenizer_failure(tmp_path):
    class FailingTokenizer:
        source = 'local'
        def count(self, text: str) -> int:
            raise RuntimeError('tiktoken not installed')

    path = create_task(
        task_fields=_MINIMAL_FIELDS,
        tokenizer=FailingTokenizer(),
        tokenizer_source='local',
        hostname='',
        backend='llama-server',
        agent_name='hermes',
        model='',
        cwd=str(tmp_path),
    )
    assert 'unavailable-via-local' in path.read_text()


def test_create_task_short_code_is_fourteen_digits(tmp_path):
    path = create_task(
        task_fields=_MINIMAL_FIELDS,
        tokenizer=FakeTokenizer(),
        tokenizer_source='local',
        hostname='',
        backend='llama-server',
        agent_name='hermes',
        model='',
        cwd=str(tmp_path),
    )
    task = from_toml(path.read_text())
    assert re.fullmatch(r'\d{14}', task.short_code)


def test_create_task_short_code_matches_filename_timestamp(tmp_path):
    # created, the filename timestamp, and short_code all come from one
    # captured instant — the filename's timestamp, with its separators
    # stripped, must equal short_code exactly.
    path = create_task(
        task_fields=_MINIMAL_FIELDS,
        tokenizer=FakeTokenizer(),
        tokenizer_source='local',
        hostname='',
        backend='llama-server',
        agent_name='hermes',
        model='',
        cwd=str(tmp_path),
    )
    task = from_toml(path.read_text())
    # Filename timestamp is %Y-%m-%dT%H-%M-%S: 5 dash-separated parts before
    # the slug begins. Strip everything but digits from those parts.
    parts = path.name.split('-', 5)[:5]
    digits_from_filename = re.sub(r'\D', '', '-'.join(parts))
    assert digits_from_filename == task.short_code


def test_create_task_short_code_is_utc_not_local(tmp_path):
    before = datetime.now(timezone.utc)
    path = create_task(
        task_fields=_MINIMAL_FIELDS,
        tokenizer=FakeTokenizer(),
        tokenizer_source='local',
        hostname='',
        backend='llama-server',
        agent_name='hermes',
        model='',
        cwd=str(tmp_path),
    )
    after = datetime.now(timezone.utc)
    task = from_toml(path.read_text())
    short_code_instant = datetime.strptime(task.short_code, '%Y%m%d%H%M%S').replace(tzinfo=timezone.utc)
    assert before.replace(microsecond=0) <= short_code_instant <= after.replace(microsecond=0)


def test_create_task_invalid_fields_raises(tmp_path):
    with pytest.raises(Exception):
        create_task(
            task_fields={'title': 'missing required fields'},
            tokenizer=FakeTokenizer(),
            tokenizer_source='local',
            hostname='',
            backend='llama-server',
            agent_name='hermes',
            model='',
            cwd=str(tmp_path),
        )
