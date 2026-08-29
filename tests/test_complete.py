import pytest
from pathlib import Path

from complete import complete_task
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


# ── complete_task ─────────────────────────────────────────────────────────────

def test_complete_task_moves_file_to_completed(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = complete_task(task_file, 'Done', 'pass', 'task.py', tmp_path)
    assert dest.exists()
    assert 'completed' in str(dest)
    assert not task_file.exists()


def test_complete_task_updates_status(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = complete_task(task_file, 'Done', 'pass', 'task.py', tmp_path)
    assert from_toml(dest.read_text()).status == TaskState.completed


def test_complete_task_fills_results_section(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = complete_task(task_file, 'All done', '5 pass', 'foo.py', tmp_path)
    results = from_toml(dest.read_text()).results
    assert results['summary'] == 'All done'
    assert results['tests'] == '5 pass'
    assert results['files_changed'] == 'foo.py'


def test_complete_task_preserves_filename(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = complete_task(task_file, 'Done', 'pass', 'task.py', tmp_path)
    assert dest.name == task_file.name


def test_complete_task_raises_when_already_completed(tmp_path):
    task_file = _make_task_file(tmp_path, status='completed')
    with pytest.raises(ValueError):
        complete_task(task_file, 'Done', 'pass', 'foo.py', tmp_path)


def test_complete_task_from_deprecated_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='deprecated')
    with pytest.raises(ValueError):
        complete_task(task_file, 'Done', 'pass', 'foo.py', tmp_path)


def test_complete_task_appends_to_dev_log(tmp_path):
    task_file = _make_task_file(tmp_path)
    dev_log = tmp_path / 'development-log.md'
    dev_log.write_text('# Development Log\n')
    complete_task(task_file, 'Did it', 'pass', 'foo.py', tmp_path)
    content = dev_log.read_text()
    assert 'Test Task' in content
    assert 'Did it' in content


def test_complete_task_skips_dev_log_when_absent(tmp_path):
    task_file = _make_task_file(tmp_path)
    complete_task(task_file, 'Done', 'pass', 'foo.py', tmp_path)
    assert not (tmp_path / 'development-log.md').exists()
