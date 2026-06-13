import pytest
from pathlib import Path

from complete import complete_task, _read_status, _read_title, _set_status, _fill_results
from workflow import TaskState


def _make_task_file(tmp_path: Path, status: str = 'in_progress') -> Path:
    pending_dir = tmp_path / 'tasks' / 'pending'
    pending_dir.mkdir(parents=True)
    task_file = pending_dir / '2026-06-13T00-00-00-test-task.md'
    task_file.write_text(
        f'# Test Task\n\n'
        f'**Created:** 2026-06-13\n'
        f'**Model:** qwen3-coder-30b\n'
        f'**Agent:** `pond-qwen-hermes`\n'
        f'**Status:** {status}\n\n'
        f'## Goal\n\nDo a thing.\n\n'
        f'## Results\n'
        f'<!-- Filled in by the executing model after completion -->\n'
        f'**Tests:**\n'
        f'**Files changed:**\n'
        f'**Summary:**\n'
    )
    return task_file


# ── helpers ───────────────────────────────────────────────────────────────────

def test_read_status_pending():
    assert _read_status('**Status:** pending') == TaskState.pending


def test_read_status_treats_planned_as_pending():
    assert _read_status('**Status:** planned') == TaskState.pending


def test_read_status_in_progress():
    assert _read_status('**Status:** in_progress') == TaskState.in_progress


def test_read_status_missing_raises():
    with pytest.raises(ValueError, match=r'No \*\*Status'):
        _read_status('no status here')


def test_read_title_extracts_h1():
    assert _read_title('# My Task\n\n**Status:** pending') == 'My Task'


def test_read_title_returns_untitled_when_absent():
    assert _read_title('**Status:** pending') == 'Untitled'


def test_set_status_replaces_line():
    content = '**Status:** pending\n'
    result = _set_status(content, TaskState.completed)
    assert '**Status:** completed' in result
    assert 'pending' not in result


def test_fill_results_replaces_entire_section():
    content = (
        '## Goal\n\nDo a thing.\n\n'
        '## Results\n'
        '<!-- Filled in by the executing model after completion -->\n'
        '**Tests:**\n'
        '**Files changed:**\n'
        '**Summary:**\n'
    )
    result = _fill_results(content, 'It worked', '5 pass', 'foo.py')
    assert '**Summary:** It worked' in result
    assert '**Tests:** 5 pass' in result
    assert '**Files changed:** foo.py' in result
    assert '<!-- Filled in' not in result


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
    assert '**Status:** completed' in dest.read_text()


def test_complete_task_fills_results_section(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = complete_task(task_file, 'All done', '5 pass', 'foo.py', tmp_path)
    content = dest.read_text()
    assert '**Summary:** All done' in content
    assert '**Tests:** 5 pass' in content
    assert '**Files changed:** foo.py' in content


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
