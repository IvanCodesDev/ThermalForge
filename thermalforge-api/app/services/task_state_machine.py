from app.domain.enums import TaskStatus
from app.domain.errors import InvalidStateTransition


class TaskStateMachine:
    _forward_transitions: dict[TaskStatus, frozenset[TaskStatus]] = {
        TaskStatus.CREATED: frozenset({TaskStatus.UPLOADED}),
        TaskStatus.UPLOADED: frozenset({TaskStatus.PARSING}),
        TaskStatus.PARSING: frozenset(
            {TaskStatus.AWAITING_INPUT, TaskStatus.BRIEFING}
        ),
        TaskStatus.AWAITING_INPUT: frozenset({TaskStatus.BRIEFING}),
        TaskStatus.BRIEFING: frozenset(
            {TaskStatus.AWAITING_INPUT, TaskStatus.THERMAL_ANALYSIS}
        ),
        TaskStatus.THERMAL_ANALYSIS: frozenset({TaskStatus.CONCEPT_IMAGING}),
        TaskStatus.CONCEPT_IMAGING: frozenset({TaskStatus.MULTIVIEW_IMAGING}),
        TaskStatus.MULTIVIEW_IMAGING: frozenset({TaskStatus.MULTIVIEW_REVIEW}),
        TaskStatus.MULTIVIEW_REVIEW: frozenset(
            {TaskStatus.MULTIVIEW_IMAGING, TaskStatus.MODELING}
        ),
        TaskStatus.MODELING: frozenset({TaskStatus.MODEL_REVIEW}),
        TaskStatus.MODEL_REVIEW: frozenset(
            {TaskStatus.MODELING, TaskStatus.READY}
        ),
        TaskStatus.READY: frozenset(),
        TaskStatus.FAILED: frozenset(
            {
                TaskStatus.CREATED,
                TaskStatus.UPLOADED,
                TaskStatus.PARSING,
                TaskStatus.BRIEFING,
                TaskStatus.THERMAL_ANALYSIS,
                TaskStatus.CONCEPT_IMAGING,
                TaskStatus.MULTIVIEW_IMAGING,
                TaskStatus.MULTIVIEW_REVIEW,
                TaskStatus.MODELING,
                TaskStatus.MODEL_REVIEW,
            }
        ),
        TaskStatus.CANCELLED: frozenset(
            {TaskStatus.CREATED, TaskStatus.UPLOADED}
        ),
    }

    def transition(
        self,
        current: TaskStatus,
        target: TaskStatus,
    ) -> TaskStatus:
        if current == target:
            return current

        if target == TaskStatus.CANCELLED and current not in {
            TaskStatus.READY,
            TaskStatus.CANCELLED,
        }:
            return target

        if target == TaskStatus.FAILED and current not in {
            TaskStatus.READY,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        }:
            return target

        if target not in self._forward_transitions[current]:
            raise InvalidStateTransition(current.value, target.value)

        return target
