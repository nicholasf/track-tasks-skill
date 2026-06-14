import pytest
from pathlib import Path

from mark_as_hallucinated import mark_as_hallucinated, _read_status, _add_hallucinated_by
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


# ── helpers ───────────────────────────────────────────────────────────────────

def test_read_status_treats_planned_as_pending():
    assert _read_status('**Status:** planned') == TaskState.pending


def test_add_hallucinated_by_inserts_after_status():
    content = '**Status:** hallucinated\n## Goal\n'
    result = _add_hallucinated_by(content, 'gollum-qwen3')
    lines = result.splitlines()
    status_index = next(i for i, l in enumerate(lines) if '**Status:**' in l)
    assert '**Hallucinated by:**' in lines[status_index + 1]


# ── mark_as_hallucinated ──────────────────────────────────────────────────────

def test_moves_file_to_hallucinated_dir(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = mark_as_hallucinated(task_file, 'The LLM claimed it refactored X', '', tmp_path)
    assert dest.exists()
    assert 'hallucinated' in str(dest)
    assert not task_file.exists()


def test_updates_status(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = mark_as_hallucinated(task_file, 'Claimed solution', '', tmp_path)
    assert '**Status:** hallucinated' in dest.read_text()


def test_fills_results_with_solution(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = mark_as_hallucinated(task_file, 'The full claimed solution text', '', tmp_path)
    content = dest.read_text()
    assert 'The full claimed solution text' in content
    assert '**Hallucinated solution:**' in content


def test_adds_hallucinated_by_when_provided(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = mark_as_hallucinated(task_file, 'Solution', 'gollum-qwen3', tmp_path)
    assert '**Hallucinated by:** gollum-qwen3' in dest.read_text()


def test_omits_hallucinated_by_when_empty(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = mark_as_hallucinated(task_file, 'Solution', '', tmp_path)
    assert '**Hallucinated by:**' not in dest.read_text()


def test_preserves_filename(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = mark_as_hallucinated(task_file, 'Solution', '', tmp_path)
    assert dest.name == task_file.name


def test_already_hallucinated_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='hallucinated')
    with pytest.raises(ValueError):
        mark_as_hallucinated(task_file, 'Again', '', tmp_path)


def test_completed_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='completed')
    with pytest.raises(ValueError):
        mark_as_hallucinated(task_file, 'Nope', '', tmp_path)


def test_deprecated_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='deprecated')
    with pytest.raises(ValueError):
        mark_as_hallucinated(task_file, 'Nope', '', tmp_path)


def test_in_progress_can_be_hallucinated(tmp_path):
    task_file = _make_task_file(tmp_path, status='in_progress')
    dest = mark_as_hallucinated(task_file, 'Mid-flight hallucination', '', tmp_path)
    assert dest.exists()


def test_appends_to_dev_log(tmp_path):
    task_file = _make_task_file(tmp_path)
    dev_log = tmp_path / 'development-log.md'
    dev_log.write_text('# Development Log\n')
    mark_as_hallucinated(task_file, 'The claimed solution', '', tmp_path)
    content = dev_log.read_text()
    assert 'Test Task' in content
    assert 'The claimed solution' in content
    assert 'hallucinated' in content


def test_skips_dev_log_when_absent(tmp_path):
    task_file = _make_task_file(tmp_path)
    mark_as_hallucinated(task_file, 'Solution', '', tmp_path)
    assert not (tmp_path / 'development-log.md').exists()
