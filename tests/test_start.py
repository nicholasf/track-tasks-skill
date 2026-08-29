import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch

from start import start_task
from task import ExecutionMode, Task, from_toml, to_toml
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


def _fake_git_success(*args, **kwargs):
    return MagicMock(returncode=0, stderr='')


def _fake_git_failure(*args, **kwargs):
    return MagicMock(returncode=128, stderr="fatal: a branch named 'task/exists' already exists")


# ── non-worktree modes ────────────────────────────────────────────────────────

def test_start_sets_execution_mode_local(tmp_path):
    task_file = _make_task_file(tmp_path)
    start_task(task_file, ExecutionMode.local, '', '', tmp_path)
    assert from_toml(task_file.read_text()).execution_mode == ExecutionMode.local


def test_start_sets_execution_mode_ask_llm(tmp_path):
    task_file = _make_task_file(tmp_path)
    start_task(task_file, ExecutionMode.ask_llm, '', '', tmp_path)
    assert from_toml(task_file.read_text()).execution_mode == ExecutionMode.ask_llm


def test_start_sets_execution_mode_ask_agent(tmp_path):
    task_file = _make_task_file(tmp_path)
    start_task(task_file, ExecutionMode.ask_agent, '', '', tmp_path)
    assert from_toml(task_file.read_text()).execution_mode == ExecutionMode.ask_agent


def test_start_transitions_status_to_in_progress(tmp_path):
    task_file = _make_task_file(tmp_path)
    start_task(task_file, ExecutionMode.local, '', '', tmp_path)
    assert from_toml(task_file.read_text()).status == TaskState.in_progress


def test_start_leaves_file_in_pending_dir(tmp_path):
    task_file = _make_task_file(tmp_path)
    dest = start_task(task_file, ExecutionMode.local, '', '', tmp_path)
    assert dest == task_file
    assert 'pending' in str(dest)
    assert dest.exists()


def test_start_from_in_progress_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='in_progress')
    with pytest.raises(ValueError):
        start_task(task_file, ExecutionMode.local, '', '', tmp_path)


def test_start_from_completed_raises(tmp_path):
    task_file = _make_task_file(tmp_path, status='completed')
    with pytest.raises(ValueError):
        start_task(task_file, ExecutionMode.local, '', '', tmp_path)


# ── local_worktree mode ───────────────────────────────────────────────────────

def test_start_worktree_requires_path_and_branch(tmp_path):
    task_file = _make_task_file(tmp_path)
    with pytest.raises(ValueError):
        start_task(task_file, ExecutionMode.local_worktree, '', '', tmp_path)


def test_start_worktree_requires_branch_when_path_given(tmp_path):
    task_file = _make_task_file(tmp_path)
    with pytest.raises(ValueError):
        start_task(task_file, ExecutionMode.local_worktree, '../wt', '', tmp_path)


def test_start_worktree_calls_git_worktree_add(tmp_path):
    task_file = _make_task_file(tmp_path)
    with patch('start.subprocess.run', side_effect=_fake_git_success) as run:
        start_task(task_file, ExecutionMode.local_worktree, '../wt-test', 'task/smoke-test', tmp_path)
    run.assert_called_once_with(
        ['git', 'worktree', 'add', '../wt-test', '-b', 'task/smoke-test'],
        cwd=tmp_path, capture_output=True, text=True,
    )


def test_start_worktree_records_path_and_branch(tmp_path):
    task_file = _make_task_file(tmp_path)
    with patch('start.subprocess.run', side_effect=_fake_git_success):
        start_task(task_file, ExecutionMode.local_worktree, '../wt-test', 'task/smoke-test', tmp_path)
    task = from_toml(task_file.read_text())
    assert task.worktree_path == '../wt-test'
    assert task.worktree_branch == 'task/smoke-test'
    assert task.execution_mode == ExecutionMode.local_worktree


def test_start_worktree_git_failure_raises_and_does_not_mutate_task(tmp_path):
    task_file = _make_task_file(tmp_path)
    original = task_file.read_text()
    with patch('start.subprocess.run', side_effect=_fake_git_failure):
        with pytest.raises(RuntimeError, match='already exists'):
            start_task(task_file, ExecutionMode.local_worktree, '../wt-test', 'task/exists', tmp_path)
    assert task_file.read_text() == original
