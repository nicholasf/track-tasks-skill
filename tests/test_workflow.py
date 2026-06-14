import pytest
from workflow import TaskState, TRANSITIONS, transition


def test_taskstate_values_are_strings():
    assert TaskState.pending == 'pending'
    assert TaskState.in_progress == 'in_progress'
    assert TaskState.completed == 'completed'
    assert TaskState.deprecated == 'deprecated'
    assert TaskState.hallucinated == 'hallucinated'


def test_pending_can_transition_to_in_progress():
    transition(TaskState.pending, TaskState.in_progress)


def test_pending_can_transition_to_deprecated():
    transition(TaskState.pending, TaskState.deprecated)


def test_pending_cannot_transition_to_completed():
    with pytest.raises(ValueError, match='Cannot transition'):
        transition(TaskState.pending, TaskState.completed)


def test_in_progress_can_transition_to_completed():
    transition(TaskState.in_progress, TaskState.completed)


def test_in_progress_can_transition_to_deprecated():
    transition(TaskState.in_progress, TaskState.deprecated)


def test_in_progress_cannot_transition_to_pending():
    with pytest.raises(ValueError):
        transition(TaskState.in_progress, TaskState.pending)


def test_completed_cannot_transition_anywhere():
    with pytest.raises(ValueError):
        transition(TaskState.completed, TaskState.pending)


def test_deprecated_cannot_transition_anywhere():
    with pytest.raises(ValueError):
        transition(TaskState.deprecated, TaskState.pending)


def test_pending_can_transition_to_hallucinated():
    transition(TaskState.pending, TaskState.hallucinated)


def test_in_progress_can_transition_to_hallucinated():
    transition(TaskState.in_progress, TaskState.hallucinated)


def test_hallucinated_cannot_transition_anywhere():
    with pytest.raises(ValueError):
        transition(TaskState.hallucinated, TaskState.pending)


def test_transition_error_message_names_valid_transitions():
    with pytest.raises(ValueError, match='in_progress|deprecated'):
        transition(TaskState.pending, TaskState.completed)
