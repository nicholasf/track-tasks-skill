from enum import StrEnum


class TaskState(StrEnum):
    pending = 'pending'
    in_progress = 'in_progress'
    completed = 'completed'
    deprecated = 'deprecated'


TRANSITIONS: dict[TaskState, set[TaskState]] = {
    TaskState.pending: {TaskState.in_progress, TaskState.deprecated},
    TaskState.in_progress: {TaskState.completed, TaskState.deprecated},
    TaskState.completed: set(),
    TaskState.deprecated: set(),
}


def transition(current: TaskState, target: TaskState) -> None:
    if target not in TRANSITIONS.get(current, set()):
        valid = ', '.join(s.value for s in TRANSITIONS.get(current, set())) or 'none'
        raise ValueError(
            f"Cannot transition from '{current}' to '{target}'. "
            f"Valid transitions from '{current}': {valid}"
        )
