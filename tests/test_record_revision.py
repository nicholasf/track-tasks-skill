from pathlib import Path

import pytest

from record_failure import record_failure
from record_revision import record_revision
from task import Failure, Revision, Task, from_toml, to_toml
from workflow import TaskState


def _make_task_file(tmp_path: Path, status: str = 'in_progress') -> Path:
    pending_dir = tmp_path / 'tasks' / 'pending'
    pending_dir.mkdir(parents=True)
    task_file = pending_dir / '2026-09-12T00-00-00-test-task.toml'
    task_file.write_text(to_toml(Task.model_validate({
        'title': 'Test Task', 'goal': 'Do a thing.', 'model': 'qwen3.8-27b',
        'agent': 'pond-qwen', 'created': '2026-09-12', 'status': status,
    })))
    return task_file


def _fail(task_file: Path, tmp_path: Path) -> None:
    record_failure(task_file, 'pond-qwen', 'qwen3.8', 'L1', 'ran out', 'log', tmp_path)


def _revise(task_file: Path, tmp_path: Path, instructions: str = 'Do it differently.') -> Path:
    return record_revision(task_file, 'claude', 'L1 re-estimated', instructions, tmp_path)


def test_revision_returns_task_to_pending(tmp_path):
    task_file = _make_task_file(tmp_path)
    _fail(task_file, tmp_path)
    _revise(task_file, tmp_path)
    assert from_toml(task_file.read_text()).status == TaskState.pending


def test_revision_numbering_continues_after_a_failure(tmp_path):
    task_file = _make_task_file(tmp_path)
    _fail(task_file, tmp_path)
    _revise(task_file, tmp_path)
    task = from_toml(task_file.read_text())
    assert list(task.sections) == ['1', '2']
    assert isinstance(task.sections['1'], Failure)
    assert isinstance(task.sections['2'], Revision)


def test_revision_preserves_instructions(tmp_path):
    task_file = _make_task_file(tmp_path)
    _fail(task_file, tmp_path)
    _revise(task_file, tmp_path, 'Edit command.md, not SKILL.md.')
    section = from_toml(task_file.read_text()).sections['2']
    assert section.instructions == 'Edit command.md, not SKILL.md.'
    assert section.agent == 'claude'
    assert section.complexity == 'L1 re-estimated'


def test_revision_updates_latest_section(tmp_path):
    task_file = _make_task_file(tmp_path)
    _fail(task_file, tmp_path)
    assert from_toml(task_file.read_text()).latest_section == '1'
    _revise(task_file, tmp_path)
    assert from_toml(task_file.read_text()).latest_section == '2'


def test_revision_does_not_edit_the_task_text(tmp_path):
    task_file = _make_task_file(tmp_path)
    before = from_toml(task_file.read_text())
    _fail(task_file, tmp_path)
    _revise(task_file, tmp_path)
    after = from_toml(task_file.read_text())
    assert after.title == before.title
    assert after.goal == before.goal
    assert after.changes == before.changes


def test_revision_file_stays_in_pending(tmp_path):
    task_file = _make_task_file(tmp_path)
    _fail(task_file, tmp_path)
    dest = _revise(task_file, tmp_path)
    assert dest == task_file
    assert 'pending' in str(dest)


def test_revision_on_a_task_that_did_not_fail_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='completed')
    with pytest.raises(ValueError):
        _revise(task_file, tmp_path)


def test_revision_timestamps_describe_one_instant(tmp_path):
    from datetime import datetime
    task_file = _make_task_file(tmp_path)
    _fail(task_file, tmp_path)
    _revise(task_file, tmp_path)
    section = from_toml(task_file.read_text()).sections['2']
    at_utc = datetime.fromisoformat(section.at_utc)
    assert section.at_local == at_utc.astimezone().strftime('%Y-%m-%d %H:%M:%S %Z')


def test_revision_appends_to_dev_log(tmp_path):
    task_file = _make_task_file(tmp_path)
    (tmp_path / 'development-log.md').write_text('# Development Log\n')
    _fail(task_file, tmp_path)
    _revise(task_file, tmp_path, 'CORRECTION TEXT')
    assert 'CORRECTION TEXT' in (tmp_path / 'development-log.md').read_text()
