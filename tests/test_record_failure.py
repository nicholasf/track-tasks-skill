from datetime import datetime
from pathlib import Path

import pytest

from record_failure import record_failure
from task import Task, from_toml, to_toml
from workflow import TaskState


def _make_task_file(tmp_path: Path, status: str = 'in_progress') -> Path:
    pending_dir = tmp_path / 'tasks' / 'pending'
    pending_dir.mkdir(parents=True)
    task_file = pending_dir / '2026-06-13T00-00-00-test-task.toml'
    task = Task.model_validate({
        'title': 'Test Task',
        'goal': 'Do a thing.',
        'model': 'qwen3-coder-30b',
        'agent': 'pond-qwen-hermes',
        'created': '2026-06-13',
        'status': status,
    })
    task_file.write_text(to_toml(task))
    return task_file


def _record(task_file: Path, tmp_path: Path) -> Path:
    return record_failure(
        task_file,
        'pond-qwen',
        'qwen3.8-27b',
        'L1 ~16,481',
        'Tests failed: 2 errors',
        'AssertionError: boom',
        tmp_path,
    )


# ── record_failure ────────────────────────────────────────────────────────────

def test_record_failure_sets_status_to_failed(tmp_path):
    task_file = _make_task_file(tmp_path)
    record_failure(task_file, 'pond-qwen', 'qwen3.8-27b', 'L1', 'Tests failed', 'log', tmp_path)
    assert from_toml(task_file.read_text()).status == TaskState.failed


def test_record_failure_first_section_keyed_1(tmp_path):
    task_file = _make_task_file(tmp_path)
    _record(task_file, tmp_path)
    task = from_toml(task_file.read_text())
    assert list(task.sections) == ['1']
    section = task.sections['1']
    assert section.type == 'failure'
    assert section.agent == 'pond-qwen'
    assert section.model == 'qwen3.8-27b'
    assert section.complexity == 'L1 ~16,481'
    assert section.outcome == 'Tests failed: 2 errors'
    assert section.log == 'AssertionError: boom'


def test_record_failure_second_failure_adds_section_2(tmp_path):
    task_file = _make_task_file(tmp_path)
    _record(task_file, tmp_path)
    # A failed task must be retried (failed -> in_progress) before it can fail again.
    task = from_toml(task_file.read_text())
    task_file.write_text(to_toml(task.model_copy(update={'status': TaskState.in_progress})))
    _record(task_file, tmp_path)
    task = from_toml(task_file.read_text())
    assert list(task.sections) == ['1', '2']
    assert task.sections['1'].outcome == 'Tests failed: 2 errors'
    assert task.sections['2'].outcome == 'Tests failed: 2 errors'
    assert task.status == TaskState.failed


def test_record_failure_file_stays_in_pending(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _record(task_file, tmp_path)
    assert dest == task_file
    assert task_file.exists()
    assert 'pending' in str(task_file)
    assert not (tmp_path / 'tasks' / 'failed').exists()


def test_record_failure_at_utc_and_at_local_same_instant(tmp_path):
    task_file = _make_task_file(tmp_path)
    _record(task_file, tmp_path)
    section = from_toml(task_file.read_text()).sections['1']
    at_utc = datetime.fromisoformat(section.at_utc)
    assert at_utc.utcoffset() is not None

    # at_local is a readable local form, not ISO — so it cannot be parsed back
    # and compared. Instead, derive what it should be from at_utc: if the two
    # describe the same instant, this reproduces it exactly.
    assert section.at_local == at_utc.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')


def test_record_failure_at_local_is_readable(tmp_path):
    task_file = _make_task_file(tmp_path)
    _record(task_file, tmp_path)
    at_local = from_toml(task_file.read_text()).sections['1'].at_local
    assert at_local[10] == ' '           # date and time separated by a space, not 'T'
    assert '.' not in at_local           # no microseconds
    assert at_local[-1].isalpha()        # ends in a zone abbreviation


def test_record_failure_pending_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='pending')
    with pytest.raises(ValueError):
        _record(task_file, tmp_path)


def test_record_failure_completed_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='completed')
    with pytest.raises(ValueError):
        _record(task_file, tmp_path)


def test_record_failure_deprecated_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='deprecated')
    with pytest.raises(ValueError):
        _record(task_file, tmp_path)


def test_record_failure_appends_to_dev_log(tmp_path):
    task_file = _make_task_file(tmp_path)
    dev_log = tmp_path / 'development-log.md'
    dev_log.write_text('# Development Log\n')
    _record(task_file, tmp_path)
    content = dev_log.read_text()
    assert 'Test Task' in content
    assert 'Tests failed: 2 errors' in content
    assert 'failed' in content


def test_record_failure_skips_dev_log_when_absent(tmp_path):
    task_file = _make_task_file(tmp_path)
    _record(task_file, tmp_path)
    assert not (tmp_path / 'development-log.md').exists()
