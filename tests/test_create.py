import os
import pytest
from pathlib import Path
from unittest.mock import patch

from create import _slug, create_task
from task import Task, render


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
    assert '# Add logging to gate' in path.read_text()


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
    assert 'local tokenizer failed' in path.read_text()


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
