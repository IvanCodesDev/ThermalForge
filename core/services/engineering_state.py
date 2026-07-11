"""EngineeringState 与 ArtifactRegistry 的线程安全内存服务。"""
from __future__ import annotations

from pathlib import Path
from threading import RLock

from core.config import PROJECT_ROOT, get_settings
from core.models.engineering_state import (
    Approval,
    Artifact,
    ArtifactFidelity,
    ArtifactLineage,
    ArtifactRegistry,
    EngineeringState,
)
from core.models.agent_pipeline import EvidenceRef
from core.persistence import DocumentNotFoundError, SQLiteDocumentStore


class EngineeringStateNotFoundError(LookupError):
    pass


class EngineeringStateConflictError(ValueError):
    pass


class EngineeringStateGateError(PermissionError):
    pass


class EngineeringStateService:
    def __init__(self, store: SQLiteDocumentStore | None = None) -> None:
        settings = get_settings()
        if store is None and settings.is_real:
            configured = Path(settings.database_path)
            store = SQLiteDocumentStore(configured if configured.is_absolute() else PROJECT_ROOT / configured)
        self._store = store
        self._states: dict[str, list[EngineeringState]] = {}
        self._artifacts: dict[str, dict[str, Artifact]] = {}
        self._lock = RLock()

    def put(self, state: EngineeringState, *, expected_revision: int) -> EngineeringState:
        with self._lock:
            try:
                current_revision = self._require_current(state.project_id).revision
            except EngineeringStateNotFoundError:
                current_revision = 0
            if current_revision != expected_revision:
                raise EngineeringStateConflictError(
                    f"project revision 已是 {current_revision}，不是 {expected_revision}"
                )
            next_revision = current_revision + 1
            if state.revision not in {expected_revision, next_revision}:
                raise EngineeringStateConflictError(
                    f"state.revision 必须为 {expected_revision} 或 {next_revision}"
                )
            updated = state.model_copy(update={"revision": next_revision})
            self._save_state(updated)
            return updated.model_copy(deep=True)

    def get(self, project_id: str, revision: int | None = None) -> EngineeringState:
        with self._lock:
            if self._store is not None:
                try:
                    return EngineeringState.model_validate(
                        self._store.get("engineering_state", project_id, revision)
                    )
                except DocumentNotFoundError as exc:
                    raise EngineeringStateNotFoundError(str(exc)) from exc
            history = self._states.get(project_id)
            if not history:
                raise EngineeringStateNotFoundError(f"project {project_id} 不存在")
            if revision is None:
                return history[-1].model_copy(deep=True)
            for state in history:
                if state.revision == revision:
                    return state.model_copy(deep=True)
            raise EngineeringStateNotFoundError(
                f"project {project_id} revision {revision} 不存在"
            )

    def confirm(
        self,
        project_id: str,
        *,
        expected_revision: int,
        reviewed_by: str,
        subject: str,
        evidence: list[EvidenceRef],
    ) -> EngineeringState:
        with self._lock:
            current = self._require_current(project_id)
            if current.revision != expected_revision:
                raise EngineeringStateConflictError(
                    f"project revision 已是 {current.revision}，不是 {expected_revision}"
                )
            if current.unresolved:
                raise EngineeringStateGateError("存在 unresolved 项，不能人工确认")
            next_revision = current.revision + 1
            approval = Approval(
                id=f"approval-{next_revision}",
                subject=subject,
                decision="approved",
                reviewed_by=reviewed_by,
                revision=current.revision,
                evidence=evidence,
            )
            updated = current.model_copy(update={
                "revision": next_revision,
                "approvals": current.approvals + [approval],
            })
            self._save_state(updated)
            return updated.model_copy(deep=True)

    def register_artifact(
        self,
        project_id: str,
        artifact: Artifact,
        *,
        expected_revision: int,
    ) -> Artifact:
        with self._lock:
            current = self._require_current(project_id)
            if current.revision != expected_revision:
                raise EngineeringStateConflictError(
                    f"project revision 已是 {current.revision}，不是 {expected_revision}"
                )
            if artifact.input_revision != current.revision:
                raise EngineeringStateConflictError(
                    "artifact.input_revision 必须匹配当前 EngineeringState revision"
                )
            project_artifacts = self._project_artifacts(project_id)
            if artifact.project_id not in {None, project_id}:
                raise EngineeringStateConflictError("artifact.project_id 与注册项目不匹配")
            if artifact.provider == "hyper3d" and artifact.fidelity != ArtifactFidelity.CONCEPT_MESH:
                raise EngineeringStateConflictError("Hyper3D 产物永久强制为 concept_mesh")
            for parent_id in artifact.parent_artifact_ids:
                parent = project_artifacts.get(parent_id)
                if parent is None:
                    raise EngineeringStateConflictError(f"parent artifact {parent_id} 不存在")
                if parent.fidelity == ArtifactFidelity.CONCEPT_MESH and artifact.role in {"geometry", "simulation_handoff"}:
                    raise EngineeringStateConflictError("concept_mesh 不得进入工程几何或仿真 lineage")
            existing = project_artifacts.get(artifact.id)
            normalized = artifact.model_copy(update={"project_id": project_id}) if artifact.project_id is not None else artifact
            if existing is not None:
                raise EngineeringStateConflictError(f"artifact {artifact.id} 已存在")
            if self._store is not None:
                self._store.put(
                    f"engineering_artifact:{project_id}",
                    normalized.id,
                    1,
                    normalized.model_dump(mode="json"),
                )
            else:
                project_artifacts[artifact.id] = normalized
            artifact = normalized
            return artifact.model_copy(deep=True)

    def artifacts(self, project_id: str) -> ArtifactRegistry:
        with self._lock:
            self._require_current(project_id)
            return ArtifactRegistry(
                project_id=project_id,
                artifacts=[item.model_copy(deep=True) for item in self._project_artifacts(project_id).values()],
            )

    def get_artifact(self, project_id: str, artifact_id: str) -> Artifact:
        with self._lock:
            self._require_current(project_id)
            artifact = self._project_artifacts(project_id).get(artifact_id)
            if artifact is None:
                raise EngineeringStateNotFoundError(
                    f"artifact {artifact_id} 在 project {project_id} 中不存在"
                )
            return artifact.model_copy(deep=True)

    def lineage(self, project_id: str, artifact_id: str) -> ArtifactLineage:
        with self._lock:
            root = self.get_artifact(project_id, artifact_id)
            ancestors: list[Artifact] = []
            visited: set[str] = set()
            stack = list(root.parent_artifact_ids)
            while stack:
                parent_id = stack.pop()
                if parent_id in visited:
                    continue
                visited.add(parent_id)
                parent = self.get_artifact(project_id, parent_id)
                ancestors.append(parent)
                stack.extend(parent.parent_artifact_ids)
            return ArtifactLineage(project_id=project_id, artifact=root, ancestors=ancestors)

    def _require_current(self, project_id: str) -> EngineeringState:
        if self._store is not None:
            return self.get(project_id)
        history = self._states.get(project_id)
        if not history:
            raise EngineeringStateNotFoundError(f"project {project_id} 不存在")
        return history[-1]

    def _save_state(self, state: EngineeringState) -> None:
        if self._store is not None:
            self._store.put("engineering_state", state.project_id, state.revision, state.model_dump(mode="json"))
            return
        self._states.setdefault(state.project_id, []).append(state)

    def _project_artifacts(self, project_id: str) -> dict[str, Artifact]:
        if self._store is not None:
            return {
                item.id: item
                for item in (
                    Artifact.model_validate(payload)
                    for payload in self._store.list_latest(f"engineering_artifact:{project_id}")
                )
            }
        return self._artifacts.setdefault(project_id, {})
