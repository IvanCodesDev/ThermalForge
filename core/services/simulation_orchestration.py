"""仿真 handoff、SpaceClaim 产物与 solver 结果的内存编排。"""
from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from uuid import uuid4

from core.config import PROJECT_ROOT, get_settings
from core.models.engineering_state import Artifact, ArtifactFidelity
from core.persistence import DocumentNotFoundError, SQLiteDocumentStore
from core.models.simulation_contract import (
    CompileSimulationHandoffRequest,
    ResultAcceptance,
    SimulationHandoffContract,
    SimulationResultContract,
)
from core.services.engineering_state import EngineeringStateService
from core.services.simulation_contract import SimulationContractCompiler, SimulationContractError, SimulationResultIngestor


class SimulationHandoffNotFoundError(LookupError):
    pass


class SimulationOrchestrationService:
    def __init__(self, engineering_states: EngineeringStateService, store: SQLiteDocumentStore | None = None) -> None:
        settings = get_settings()
        if store is None and settings.is_real:
            configured = Path(settings.database_path)
            store = SQLiteDocumentStore(configured if configured.is_absolute() else PROJECT_ROOT / configured)
        self.engineering_states = engineering_states
        self._store = store
        self._handoffs: dict[str, SimulationHandoffContract] = {}
        self._results: dict[str, SimulationResultContract] = {}
        self._acceptance: dict[str, ResultAcceptance] = {}
        self._lock = RLock()

    def compile(self, project_id: str, request: CompileSimulationHandoffRequest) -> tuple[str, SimulationHandoffContract]:
        state = self.engineering_states.get(project_id, request.engineering_revision)
        artifact = self.engineering_states.get_artifact(project_id, request.geometry_artifact_id)
        contract = SimulationContractCompiler().compile(
            state,
            geometry_artifact=artifact,
            created_by=request.created_by,
            model=request.model,
            joint_extensions=request.joint_extensions,
            named_selections=request.named_selections,
            contacts=request.contacts,
            mesh_plan=request.mesh_plan,
            solver_plan=request.solver_plan,
            acceptance=request.acceptance,
        )
        handoff_id = self.save_handoff(contract)
        return handoff_id, contract.model_copy(deep=True)

    def save_handoff(self, contract: SimulationHandoffContract) -> str:
        handoff_id = f"handoff-{uuid4()}"
        with self._lock:
            if self._store is not None:
                self._store.put("simulation_handoff", handoff_id, 1, contract.model_dump(mode="json"))
            else:
                self._handoffs[handoff_id] = contract
        return handoff_id

    def get(self, handoff_id: str) -> SimulationHandoffContract:
        with self._lock:
            if self._store is not None:
                try:
                    return SimulationHandoffContract.model_validate_json(
                        json.dumps(self._store.get("simulation_handoff", handoff_id))
                    )
                except DocumentNotFoundError as exc:
                    raise SimulationHandoffNotFoundError(str(exc)) from exc
            handoff = self._handoffs.get(handoff_id)
            if handoff is None:
                raise SimulationHandoffNotFoundError(f"handoff {handoff_id} 不存在")
            return handoff.model_copy(deep=True)

    def register_spaceclaim_artifacts(self, handoff_id: str, artifacts: list[Artifact]) -> list[Artifact]:
        handoff = self.get(handoff_id)
        for artifact in artifacts:
            if artifact.provider != "spaceclaim" or artifact.metadata.get("api_version") != "V251":
                raise SimulationContractError("SpaceClaim 产物必须由 V251 生成")
            if artifact.fidelity not in {ArtifactFidelity.ENGINEERING_PROXY, ArtifactFidelity.MANUFACTURING_CAD}:
                raise SimulationContractError("SpaceClaim 产物必须是 engineering_proxy 或 manufacturing_cad")
            if artifact.metadata.get("format", "").lower() not in {"step", "scdoc"}:
                raise SimulationContractError("SpaceClaim 产物格式必须是 STEP 或 SCDOC")
            self.engineering_states.register_artifact(
                handoff.project_id, artifact, expected_revision=handoff.engineering_revision
            )
        return artifacts

    def register_result(self, handoff_id: str, result: SimulationResultContract) -> ResultAcceptance:
        handoff = self.get(handoff_id)
        ingestor = SimulationResultIngestor()
        ingestor.validate_identity(result, handoff_id, handoff)
        acceptance = ingestor.evaluate_acceptance(result, handoff)
        with self._lock:
            if self._load_result(handoff_id) is not None:
                raise SimulationContractError("该 handoff 的原始结果已登记，不可覆盖")
            if self._store is not None:
                self._store.put("simulation_result", handoff_id, 1, result.model_dump(mode="json"))
                self._store.put("simulation_acceptance", handoff_id, 1, acceptance.model_dump(mode="json"))
            else:
                self._results[handoff_id] = result.model_copy(deep=True)
                self._acceptance[handoff_id] = acceptance
        return acceptance.model_copy(deep=True)

    def summary(self, handoff_id: str) -> dict[str, object]:
        handoff = self.get(handoff_id)
        with self._lock:
            result = self._load_result(handoff_id)
            acceptance = self._load_acceptance(handoff_id) if result is not None else None
        return {
            "handoff_id": handoff_id,
            "project_id": handoff.project_id,
            "engineering_revision": handoff.engineering_revision,
            "status": acceptance.status if acceptance is not None else "pending",
            "violations": [item.model_dump(mode="json") for item in acceptance.violations] if acceptance else [],
            "result_registered": result is not None,
            "cases": [case.model_dump(mode="json") for case in result.cases] if result else [],
            "warnings": list(result.warnings) if result else [],
        }

    def _load_result(self, handoff_id: str) -> SimulationResultContract | None:
        if self._store is None:
            return self._results.get(handoff_id)
        try:
            return SimulationResultContract.model_validate_json(
                json.dumps(self._store.get("simulation_result", handoff_id))
            )
        except DocumentNotFoundError:
            return None

    def _load_acceptance(self, handoff_id: str) -> ResultAcceptance | None:
        if self._store is None:
            return self._acceptance.get(handoff_id)
        try:
            return ResultAcceptance.model_validate_json(
                json.dumps(self._store.get("simulation_acceptance", handoff_id))
            )
        except DocumentNotFoundError:
            return None
