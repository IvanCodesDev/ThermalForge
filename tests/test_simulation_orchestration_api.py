from fastapi.testclient import TestClient

from core.api.app import app
from core.api.routes.engineering_state import get_engineering_state_service
from core.api.routes.simulation_orchestration import get_simulation_orchestration_service
from core.services.engineering_state import EngineeringStateService
from core.services.simulation_orchestration import SimulationOrchestrationService
from tests.test_simulation_contract import EVIDENCE, artifact, state


def request_payload(revision=2, artifact_id="cad-1"):
    return {
        "engineering_revision": revision, "geometry_artifact_id": artifact_id, "created_by": "simulation-agent", "model": "CFD",
        "joint_extensions": {"j-1": {"segment_angle_deg": 120.0, "fins": {"count": 12, "height_mm": 8.0, "thickness_mm": 1.0, "pitch_deg": 30.0}}},
        "named_selections": [{"name": "heater", "purpose": "load", "entity_type": "face"}], "contacts": [],
        "mesh_plan": {"physics": "CFD", "element_order": "linear", "global_size_mm": 1.0, "boundary_layers": 5, "convergence_study_required": True},
        "solver_plan": {"solver": "Fluent", "analysis_type": "CFD", "max_iterations": 500, "residual_target": 1e-5},
        "acceptance": {"max_temperature_c": 90.0, "max_pressure_drop_pa": 5000.0, "require_converged": True},
    }


def test_simulation_orchestration_end_to_end():
    engineering = EngineeringStateService()
    orchestration = SimulationOrchestrationService(engineering)
    app.dependency_overrides[get_engineering_state_service] = lambda: engineering
    app.dependency_overrides[get_simulation_orchestration_service] = lambda: orchestration
    client = TestClient(app)
    try:
        initial = state(approved=False).model_copy(update={"revision": 1})
        engineering.put(initial, expected_revision=0)
        engineering.register_artifact("p-1", artifact().model_copy(update={"input_revision": 1}), expected_revision=1)
        assert client.post("/api/v1/simulation-handoffs/projects/p-1", json=request_payload(1)).status_code == 409

        confirmed = client.post("/api/v1/engineering-projects/p-1/confirm", json={"expected_revision": 1, "reviewed_by": "engineer", "evidence": [EVIDENCE]})
        assert confirmed.status_code == 200
        assert confirmed.json()["revision"] == 2

        engineering.register_artifact("p-1", artifact().model_copy(update={"id": "cad-2", "input_revision": 2}), expected_revision=2)
        concept = artifact("concept_mesh").model_copy(update={"id": "mesh-1", "input_revision": 2, "role": "simulation_geometry"})
        engineering.register_artifact("p-1", concept, expected_revision=2)
        assert client.post("/api/v1/simulation-handoffs/projects/p-1", json=request_payload(2, "mesh-1")).status_code == 409

        compiled = client.post("/api/v1/simulation-handoffs/projects/p-1", json=request_payload(2, "cad-2"))
        assert compiled.status_code == 201
        handoff_id = compiled.json()["handoff_id"]
        assert client.get(f"/api/v1/simulation-handoffs/{handoff_id}").json()["geometry_generator"]["api_version"] == "V251"

        scdoc = artifact().model_copy(update={"id": "scdoc-1", "input_revision": 2, "uri": "file:///joint.scdoc", "metadata": {"api_version": "V251", "format": "SCDOC"}})
        assert client.post(f"/api/v1/simulation-handoffs/{handoff_id}/spaceclaim-artifacts", json={"artifacts": [scdoc.model_dump(mode="json")]}).status_code == 201

        result = {"schema": "thermalforge.simulation_result", "version": "1.0.0", "project_id": "p-1", "engineering_revision": 2, "handoff_id": handoff_id, "model": "CFD", "solver": "Fluent", "cases": [{"case_id": "case-1", "converged": True, "max_temperature_c": 80.0, "pressure_drop_pa": 3000.0, "max_von_mises_stress_pa": None, "min_safety_factor": None}], "artifacts": [], "warnings": []}
        assert client.post(f"/api/v1/simulation-handoffs/{handoff_id}/result", json=result).status_code == 201
        summary = client.get(f"/api/v1/simulation-handoffs/{handoff_id}/validation-summary").json()
        assert summary["status"] == "passed"
        assert summary["result_registered"] is True
    finally:
        app.dependency_overrides.clear()
