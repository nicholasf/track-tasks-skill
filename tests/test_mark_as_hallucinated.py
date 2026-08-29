import pytest
from pathlib import Path

from mark_as_hallucinated import mark_as_hallucinated
from task import Task, from_toml, to_toml
from workflow import TaskState


def _make_task_file(tmp_path: Path, status: str = 'pending') -> Path:
    pending_dir = tmp_path / 'tasks' / 'pending'
    pending_dir.mkdir(parents=True)
    task_file = pending_dir / '2026-06-14T00-00-00-test-task.toml'
    task = Task.model_validate({
        'title': 'Test Task',
        'goal': 'Do a thing.',
        'model': 'qwen3-coder-30b',
        'agent': 'pond-qwen-hermes',
        'created': '2026-06-14',
        'status': status,
    })
    task_file.write_text(to_toml(task))
    return task_file


def _call(tmp_path, task_file, **kwargs):
    defaults = dict(solution='Claimed solution', hallucinating_agent_handle='', reporter='', reason='')
    return mark_as_hallucinated(task_file, cwd=tmp_path, **{**defaults, **kwargs})


# ── mark_as_hallucinated ──────────────────────────────────────────────────────

def test_moves_file_to_hallucinated_dir(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file)
    assert dest.exists()
    assert 'hallucinated' in str(dest)
    assert not task_file.exists()


def test_updates_status(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file)
    assert from_toml(dest.read_text()).status == TaskState.hallucinated


def test_fills_results_with_solution(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file, solution='The full claimed solution text')
    assert from_toml(dest.read_text()).results['hallucinated_solution'] == 'The full claimed solution text'


def test_records_hallucinating_agent_handle(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file, hallucinating_agent_handle='pond-qwen3')
    assert from_toml(dest.read_text()).hallucinating_agent == 'pond-qwen3'


def test_records_reporter(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file, reporter='pond-reviewer')
    assert from_toml(dest.read_text()).hallucination_reporter == 'pond-reviewer'


def test_records_reason(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file, reason='No files were actually changed')
    assert from_toml(dest.read_text()).hallucination_reason == 'No files were actually changed'


def test_omits_fields_when_empty(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file)
    task = from_toml(dest.read_text())
    assert task.hallucinating_agent == ''
    assert task.hallucination_reporter == ''
    assert task.hallucination_reason == ''


def test_preserves_filename(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file)
    assert dest.name == task_file.name


def test_already_hallucinated_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='hallucinated')
    with pytest.raises(ValueError):
        _call(tmp_path, task_file)


def test_completed_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='completed')
    with pytest.raises(ValueError):
        _call(tmp_path, task_file)


def test_deprecated_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='deprecated')
    with pytest.raises(ValueError):
        _call(tmp_path, task_file)


def test_in_progress_can_be_hallucinated(tmp_path):
    task_file = _make_task_file(tmp_path, status='in_progress')
    dest = _call(tmp_path, task_file)
    assert dest.exists()


def test_appends_to_dev_log(tmp_path):
    task_file = _make_task_file(tmp_path)
    dev_log = tmp_path / 'development-log.md'
    dev_log.write_text('# Development Log\n')
    _call(tmp_path, task_file, reason='Claimed to refactor code that does not exist')
    content = dev_log.read_text()
    assert 'Test Task' in content
    assert 'Claimed to refactor code that does not exist' in content
    assert 'hallucinated' in content


def test_skips_dev_log_when_absent(tmp_path):
    task_file = _make_task_file(tmp_path)
    _call(tmp_path, task_file)
    assert not (tmp_path / 'development-log.md').exists()
