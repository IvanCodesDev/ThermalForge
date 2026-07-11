from __future__ import annotations

from core.models.agent_pipeline import CreatePipelineRequest, SourceAsset, SourceKind
from core.persistence.sqlite_store import SQLiteDocumentStore
from core.services.agent_pipeline import AgentPipelineRuntime
from core.services.engineering_state import EngineeringStateService
from core.services.simulation_orchestration import SimulationOrchestrationService
from core.models.simulation_contract import SimulationResultContract
from tests.test_simulation_contract import artifact, compile_handoff, state


def test_engineering_state_and_artifacts_survive_service_restart(tmp_path) -> None:
    store = SQLiteDocumentStore(tmp_path / "thermalforge.db")
    first = EngineeringStateService(store=store)
    saved = first.put(state(approved=False).model_copy(update={"revision": 1}), expected_revision=0)
    first.register_artifact(
        saved.project_id,
        artifact().model_copy(update={"input_revision": saved.revision}),
        expected_revision=saved.revision,
    )

    restarted = EngineeringStateService(store=SQLiteDocumentStore(tmp_path / "thermalforge.db"))
    assert restarted.get(saved.project_id).revision == saved.revision
    assert restarted.get_artifact(saved.project_id, "cad-1").content_hash == artifact().content_hash


def test_agent_pipeline_survives_runtime_restart(tmp_path) -> None:
    store = SQLiteDocumentStore(tmp_path / "thermalforge.db")
    first = AgentPipelineRuntime(store=store)
    created = first.create(
        CreatePipelineRequest(
            product_name="FOC arm",
            sources=[
                SourceAsset(
                    id="datasheet-1",
                    kind=SourceKind.DATASHEET,
                    uri="file:///datasheet.pdf",
                    filename="datasheet.pdf",
                )
            ],
        )
    )

    restarted = AgentPipelineRuntime(store=SQLiteDocumentStore(tmp_path / "thermalforge.db"))
    loaded = restarted.get(created.id)
    assert loaded.id == created.id
    assert loaded.revision == created.revision
    assert loaded.sources[0].id == "datasheet-1"


def test_simulation_handoff_result_and_acceptance_survive_restart(tmp_path) -> None:
    store = SQLiteDocumentStore(tmp_path / "thermalforge.db")
    engineering = EngineeringStateService(store=store)
    service = SimulationOrchestrationService(engineering, store=store)
    handoff = compile_handoff()
    handoff_id = service.save_handoff(handoff)
    result = SimulationResultContract.model_validate({
        "schema": "thermalforge.simulation_result", "version": "1.0.0",
        "project_id": "p-1", "engineering_revision": 2, "handoff_id": handoff_id,
        "model": "CFD", "solver": "Fluent",
        "cases": [{"case_id": "case-1", "converged": True, "max_temperature_c": 80.0,
                   "pressure_drop_pa": 3000.0, "max_von_mises_stress_pa": None,
                   "min_safety_factor": None}],
        "artifacts": [{"role": "report", "uri": "file:///result.json", "content_hash": "b" * 64}],
        "warnings": [],
    })
    service.register_result(handoff_id, result)

    restarted = SimulationOrchestrationService(
        EngineeringStateService(store=SQLiteDocumentStore(tmp_path / "thermalforge.db")),
        store=SQLiteDocumentStore(tmp_path / "thermalforge.db"),
    )
    assert restarted.get(handoff_id).project_id == "p-1"
    summary = restarted.summary(handoff_id)
    assert summary["result_registered"] is True
    assert summary["status"] == "passed"
