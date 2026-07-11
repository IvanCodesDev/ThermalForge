import pytest

from app.domain.enums import TaskStatus
from app.domain.errors import InvalidStateTransition
from app.services.task_state_machine import TaskStateMachine


def test_allows_the_declared_forward_transition() -> None:
    machine = TaskStateMachine()

    assert machine.transition(TaskStatus.CREATED, TaskStatus.UPLOADED) is TaskStatus.UPLOADED


def test_rejects_skipping_required_quality_gates() -> None:
    machine = TaskStateMachine()

    with pytest.raises(InvalidStateTransition):
        machine.transition(TaskStatus.BRIEFING, TaskStatus.MODELING)


def test_allows_active_tasks_to_be_cancelled() -> None:
    machine = TaskStateMachine()

    assert machine.transition(TaskStatus.PARSING, TaskStatus.CANCELLED) is TaskStatus.CANCELLED


def test_rejects_changes_after_ready() -> None:
    machine = TaskStateMachine()

    with pytest.raises(InvalidStateTransition):
        machine.transition(TaskStatus.READY, TaskStatus.MODELING)


def test_allows_failed_document_tasks_to_retry_from_uploaded() -> None:
    machine = TaskStateMachine()

    assert (
        machine.transition(TaskStatus.FAILED, TaskStatus.UPLOADED)
        is TaskStatus.UPLOADED
    )
