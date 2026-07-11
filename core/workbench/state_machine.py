"""Agent 工作台状态机；确认门是进入评估态的唯一入口。"""
from __future__ import annotations

from dataclasses import dataclass

from .contracts import WorkbenchState


class InvalidWorkbenchTransition(ValueError):
    pass


_TRANSITIONS: dict[WorkbenchState, frozenset[WorkbenchState]] = {
    WorkbenchState.DRAFT: frozenset({WorkbenchState.AWAITING_CONFIRMATION}),
    WorkbenchState.AWAITING_CONFIRMATION: frozenset({WorkbenchState.CONFIRMED, WorkbenchState.REJECTED}),
    WorkbenchState.CONFIRMED: frozenset({WorkbenchState.EVALUATING}),
    WorkbenchState.EVALUATING: frozenset({WorkbenchState.COMPLETED, WorkbenchState.FAILED}),
    WorkbenchState.COMPLETED: frozenset(),
    WorkbenchState.REJECTED: frozenset(),
    WorkbenchState.FAILED: frozenset(),
}


@dataclass(frozen=True)
class WorkbenchStateMachine:
    state: WorkbenchState

    def can_transition_to(self, target: WorkbenchState) -> bool:
        return target in _TRANSITIONS[self.state]

    def transition_to(self, target: WorkbenchState) -> "WorkbenchStateMachine":
        if not self.can_transition_to(target):
            raise InvalidWorkbenchTransition(f"不允许从 {self.state.value} 转换到 {target.value}")
        return WorkbenchStateMachine(target)
