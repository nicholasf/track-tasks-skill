import subprocess
from pathlib import Path

from task import ExecutionMode, from_toml, to_toml
from workflow import TaskState, transition


def _create_worktree(repo_root: Path, path: str, branch: str) -> None:
    result = subprocess.run(
        ['git', 'worktree', 'add', path, '-b', branch],
        cwd=repo_root, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f'git worktree add failed: {result.stderr.strip()}')


def start_task(
    task_path: Path,
    mode: ExecutionMode,
    worktree_path: str,
    worktree_branch: str,
    cwd: Path,
) -> Path:
    task = from_toml(task_path.read_text())
    transition(task.status, TaskState.in_progress)

    update = {'status': TaskState.in_progress, 'execution_mode': mode}

    if mode == ExecutionMode.local_worktree:
        if not worktree_path or not worktree_branch:
            raise ValueError('local_worktree mode requires both worktree_path and worktree_branch')
        _create_worktree(cwd, worktree_path, worktree_branch)
        update['worktree_path'] = worktree_path
        update['worktree_branch'] = worktree_branch
    else:
        # No local worktree is created for any other mode, but a branch
        # and/or a suggested worktree path are still recorded — an
        # instruction for the executing agent to act on, not something this
        # orchestrator creates or enforces itself. Unlike local_worktree,
        # worktree_path here may not exist yet; it's up to that agent
        # whether and where to create it.
        if worktree_branch:
            update['branch'] = worktree_branch
        if worktree_path:
            update['worktree_path'] = worktree_path

    task = task.model_copy(update=update)
    task_path.write_text(to_toml(task))
    return task_path
