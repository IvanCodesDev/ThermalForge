"""Agent adapter 边界和不依赖外部 SDK 的本地运行时。"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import UUID

from core.engine.generator import generate
from core.engine.thermal import evaluate
from core.models.schema import from_dict
from core.models.user_input import UserInput
from core.parameter_hub import ParameterHub

from .contracts import (
    BriefConfirmation,
    EngineeringBrief,
    EvaluationResult,
    WorkbenchCapabilities,
    WorkbenchState,
)
from .extractor import extract_engineering_brief
from .state_machine import WorkbenchStateMachine


class WorkbenchNotFoundError(LookupError):
    pass


class ConfirmationRequiredError(PermissionError):
    pass


class RevisionConflictError(ValueError):
    pass


class AgentWorkbenchAdapter(Protocol):
    """未来 Agent 框架只需实现此边界；核心契约不依赖任何 Agent SDK。"""

    def extract_brief(self, text: str) -> EngineeringBrief: ...
    def confirm_brief(self, brief_id: UUID, accepted: bool, confirmed_by: str, expected_revision: int) -> EngineeringBrief: ...
    def evaluate_brief(self, brief_id: UUID) -> EvaluationResult: ...
    def capabilities(self) -> WorkbenchCapabilities: ...


_MATERIAL_MAP = {
    "铝1060": "AlSi10Mg",
    "铝6061": "AlSi10Mg",
    "铜": "Cu",
    "钢": "AlSi10Mg",
    "工程塑料": "AlSi10Mg",
    "PCB基材": "AlSi10Mg",
}
_LIMITATIONS = [
    "仅用于概念筛选，不可替代详细热设计验证。",
    "采用集总热阻/热容估算，不解析三维流场、局部湍流或共轭传热。",
    "对流换热系数使用介质典型值，未由实际流量、风速或泵曲线标定。",
    "材料与接触热阻采用简化属性，制造公差和界面老化未建模。",
]


class LocalWorkbenchRuntime:
    """进程内 runtime；显式保存 brief 与确认记录，强制执行人工门。"""

    def __init__(self, library_path: Path):
        self._hub = ParameterHub.from_library_json(library_path)
        self._briefs: dict[UUID, EngineeringBrief] = {}
        self._confirmations: dict[UUID, BriefConfirmation] = {}
        self._lock = RLock()

    def extract_brief(self, text: str) -> EngineeringBrief:
        brief = extract_engineering_brief(text)
        with self._lock:
            self._briefs[brief.id] = brief
        return brief.model_copy(deep=True)

    def get_brief(self, brief_id: UUID) -> EngineeringBrief:
        with self._lock:
            brief = self._briefs.get(brief_id)
            if brief is None:
                raise WorkbenchNotFoundError(f"brief {brief_id} 不存在")
            return brief.model_copy(deep=True)

    def confirm_brief(self, brief_id: UUID, accepted: bool, confirmed_by: str, expected_revision: int) -> EngineeringBrief:
        with self._lock:
            brief = self._briefs.get(brief_id)
            if brief is None:
                raise WorkbenchNotFoundError(f"brief {brief_id} 不存在")
            if brief.revision != expected_revision:
                raise RevisionConflictError(f"brief revision 已是 {brief.revision}，不是 {expected_revision}")
            target = WorkbenchState.CONFIRMED if accepted else WorkbenchState.REJECTED
            next_state = WorkbenchStateMachine(brief.state).transition_to(target).state
            updated = brief.model_copy(update={"state": next_state, "revision": brief.revision + 1})
            self._briefs[brief_id] = updated
            self._confirmations[brief_id] = BriefConfirmation(
                brief_id=brief_id,
                accepted=accepted,
                confirmed_by=confirmed_by,
                revision=updated.revision,
            )
            return updated.model_copy(deep=True)

    def evaluate_brief(self, brief_id: UUID) -> EvaluationResult:
        with self._lock:
            brief = self._briefs.get(brief_id)
            confirmation = self._confirmations.get(brief_id)
            if brief is None:
                raise WorkbenchNotFoundError(f"brief {brief_id} 不存在")
            if brief.state != WorkbenchState.CONFIRMED or confirmation is None or not confirmation.accepted:
                raise ConfirmationRequiredError("必须先由用户明确确认 EngineeringBrief，才能执行评估")
            evaluating = WorkbenchStateMachine(brief.state).transition_to(WorkbenchState.EVALUATING).state
            self._briefs[brief_id] = brief.model_copy(update={"state": evaluating})

        try:
            user_input = UserInput(
                device_type=brief.device_type,
                dimensions=dict(brief.dimensions),
                power_w=brief.power_w,
                max_temp_c=brief.max_temp_c,
                material=brief.material,
                has_fan=brief.has_fan,
                max_weight_g=brief.max_weight_g,
                manufacturing=brief.manufacturing,
                ambient_temp_c=brief.ambient_temp_c,
            )
            recommended = self._hub.recommend_structure(user_input)
            params = from_dict(recommended)
            svg, geometry = generate(params)
            metrics = evaluate(
                geometry,
                power_w=brief.power_w,
                t_ambient_c=brief.ambient_temp_c,
                t_limit_c=brief.max_temp_c,
                material=_MATERIAL_MAP.get(brief.material, "AlSi10Mg"),
                medium=recommended.get("cooling_medium", "air"),
                structure_type=params.structure_type,
            )
            result = EvaluationResult(
                brief_id=brief.id,
                recommended_parameters=params.to_dict(),
                svg=svg,
                geometry=asdict(geometry),
                metrics=metrics.to_dict(),
                limitations=list(_LIMITATIONS),
            )
        except Exception:
            with self._lock:
                current = self._briefs[brief_id]
                failed = WorkbenchStateMachine(current.state).transition_to(WorkbenchState.FAILED).state
                self._briefs[brief_id] = current.model_copy(update={"state": failed})
            raise

        with self._lock:
            current = self._briefs[brief_id]
            completed = WorkbenchStateMachine(current.state).transition_to(WorkbenchState.COMPLETED).state
            self._briefs[brief_id] = current.model_copy(update={"state": completed})
        return result

    def capabilities(self) -> WorkbenchCapabilities:
        return WorkbenchCapabilities()
