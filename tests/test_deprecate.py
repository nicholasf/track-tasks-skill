import pytest
from pathlib import Path

from deprecate import deprecate_task
from task import Task, from_toml, to_toml
from workflow import TaskState


def _make_task_file(tmp_path: Path, status: str = 'pending') -> Path:
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


# ── deprecate_task ────────────────────────────────────────────────────────────

def test_deprecate_task_moves_file_to_deprecated(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = deprecate_task(task_file, 'Replaced', '', tmp_path)
    assert dest.exists()
    assert 'deprecated' in str(dest)
    assert not task_file.exists()


def test_deprecate_task_updates_status(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = deprecate_task(task_file, 'Replaced', '', tmp_path)
    assert from_toml(dest.read_text()).status == TaskState.deprecated


def test_deprecate_task_adds_deprecated_by_when_provided(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = deprecate_task(task_file, 'Replaced', '2026-06-13T12-00-00-new-task.toml', tmp_path)
    assert from_toml(dest.read_text()).deprecated_by == '2026-06-13T12-00-00-new-task.toml'


def test_deprecate_task_omits_deprecated_by_when_empty(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = deprecate_task(task_file, 'Replaced', '', tmp_path)
    assert from_toml(dest.read_text()).deprecated_by == ''


def test_deprecate_task_preserves_filename(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = deprecate_task(task_file, 'Replaced', '', tmp_path)
    assert dest.name == task_file.name


def test_deprecate_task_already_deprecated_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='deprecated')
    with pytest.raises(ValueError):
        deprecate_task(task_file, 'Again', '', tmp_path)


def test_deprecate_task_completed_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='completed')
    with pytest.raises(ValueError):
        deprecate_task(task_file, 'Nope', '', tmp_path)


def test_deprecate_task_appends_to_dev_log(tmp_path):
    task_file = _make_task_file(tmp_path)
    dev_log = tmp_path / 'development-log.md'
    dev_log.write_text('# Development Log\n')
    deprecate_task(task_file, 'Superseded by new approach', '', tmp_path)
    content = dev_log.read_text()
    assert 'Test Task' in content
    assert 'Superseded by new approach' in content
    assert 'deprecated' in content


def test_deprecate_task_skips_dev_log_when_absent(tmp_path):
    task_file = _make_task_file(tmp_path)
    deprecate_task(task_file, 'Replaced', '', tmp_path)
    assert not (tmp_path / 'development-log.md').exists()
