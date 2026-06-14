import pytest
from pathlib import Path

from mark_as_hallucinated import mark_as_hallucinated, _read_status, _add_hallucination_metadata
from workflow import TaskState


def _make_task_file(tmp_path: Path, status: str = 'pending') -> Path:
    pending_dir = tmp_path / 'tasks' / 'pending'
    pending_dir.mkdir(parents=True)
    task_file = pending_dir / '2026-06-14T00-00-00-test-task.md'
    task_file.write_text(
        f'# Test Task\n\n'
        f'**Created:** 2026-06-14\n'
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


def _call(tmp_path, task_file, **kwargs):
    defaults = dict(solution='Claimed solution', hallucinating_agent_handle='', reporter='', reason='')
    return mark_as_hallucinated(task_file, cwd=tmp_path, **{**defaults, **kwargs})


# ── helpers ───────────────────────────────────────────────────────────────────

def test_read_status_treats_planned_as_pending():
    assert _read_status('**Status:** planned') == TaskState.pending


def test_add_hallucination_metadata_inserts_after_status():
    content = '**Status:** hallucinated\n## Goal\n'
    result = _add_hallucination_metadata(content, 'pond-qwen3', 'pond-reviewer', 'No files changed')
    lines = result.splitlines()
    status_index = next(i for i, l in enumerate(lines) if '**Status:**' in l)
    assert '**Hallucinating agent:**' in lines[status_index + 1]
    assert '**Reported by:**' in lines[status_index + 2]
    assert '**Reason:**' in lines[status_index + 3]


def test_add_hallucination_metadata_omits_empty_fields():
    content = '**Status:** hallucinated\n## Goal\n'
    result = _add_hallucination_metadata(content, '', '', '')
    assert '**Hallucinating agent:**' not in result
    assert '**Reported by:**' not in result
    assert '**Reason:**' not in result


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
    assert '**Status:** hallucinated' in dest.read_text()


def test_fills_results_with_solution(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file, solution='The full claimed solution text')
    content = dest.read_text()
    assert 'The full claimed solution text' in content
    assert '**Hallucinated solution:**' in content


def test_records_hallucinating_agent_handle(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file, hallucinating_agent_handle='pond-qwen3')
    assert '**Hallucinating agent:** pond-qwen3' in dest.read_text()


def test_records_reporter(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file, reporter='pond-reviewer')
    assert '**Reported by:** pond-reviewer' in dest.read_text()


def test_records_reason(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file, reason='No files were actually changed')
    assert '**Reason:** No files were actually changed' in dest.read_text()


def test_omits_fields_when_empty(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = _call(tmp_path, task_file)
    content = dest.read_text()
    assert '**Hallucinating agent:**' not in content
    assert '**Reported by:**' not in content
    assert '**Reason:**' not in content


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
