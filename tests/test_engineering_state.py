from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.api.app import app
from core.api.routes.engineering_state import get_engineering_state_service
from core.models.agent_pipeline import EvidenceRef
from core.models.engineering_state import Artifact, EngineeringState
from core.services.engineering_state import (
    EngineeringStateConflictError,
    EngineeringStateGateError,
    EngineeringStateService,
)


EVIDENCE = {"source_id": "datasheet-1", "locator": "page:2"}


def traced(value, status="extracted"):
    return {"value": value, "status": status, "evidence": [EVIDENCE]}


def state_payload(project_id="project-1", *, unresolved=None):
    return {
        "project_id": project_id,
        "revision": 1,
        "units": {
            "length": traced("mm"),
            "angle": traced("deg"),
            "temperature": traced("C"),
            "power": traced("W"),
        },
        "coordinate_system": {
            "handedness": traced("right"),
            "up_axis": traced("z"),
            "origin_mm": traced([0, 0, 0]),
        },
        "joints": [{
            "id": "joint-1",
            "axis": traced([0, 0, 1]),
            "rotation_range_deg": traced([-90, 90]),
            "outer_radius_mm": traced(80),
            "inner_radius_mm": traced(60),
            "axial_length_mm": traced(110),
            "shell_wall_thickness_mm": traced(3),
        }],
        "components": [],
        "materials": [],
        "interfaces": [],
        "thermal_loads": [],
        "operating_cases": [],
        "approvals": [],
        "unresolved": unresolved or [],
    }


def artifact_payload(input_revision=1, **overrides):
    payload = {
        "id": "cad-1",
        "role": "manufacturing_cad",
        "uri": "file:///joint.step",
        "provider": "spaceclaim",
        "fidelity": "manufacturing_cad",
        "content_hash": "a" * 64,
        "producer": "cad-agent",
        "version": "1.0.0",
        "input_revision": input_revision,
        "task_uuid": "task-1",
        "metadata": {"format": "step"},
    }
    payload.update(overrides)
    return payload


def test_contract_is_strict_and_all_joint_values_are_traced():
    state = EngineeringState.model_validate(state_payload())
    assert state.joints[0].shell_wall_thickness_mm.evidence[0].source_id == "datasheet-1"

    missing_status = state_payload()
    del missing_status["joints"][0]["axis"]["status"]
    with pytest.raises(ValidationError):
        EngineeringState.model_validate(missing_status)

    extra = state_payload()
    extra["unexpected"] = True
    with pytest.raises(ValidationError, match="extra_forbidden"):
        EngineeringState.model_validate(extra)


def test_joint_geometry_validation():
    payload = state_payload()
    payload["joints"][0]["inner_radius_mm"] = traced(81)
    with pytest.raises(ValidationError, match="inner_radius_mm"):
        EngineeringState.model_validate(payload)


def test_optimistic_revision_history_and_human_confirmation():
    service = EngineeringStateService()
    created = service.put(EngineeringState.model_validate(state_payload()), expected_revision=0)
    assert created.revision == 1

    with pytest.raises(EngineeringStateConflictError):
        service.put(created, expected_revision=0)

    confirmed = service.confirm(
        "project-1",
        expected_revision=1,
        reviewed_by="engineer",
        subject="engineering_state",
        evidence=[EvidenceRef.model_validate(EVIDENCE)],
    )
    assert confirmed.revision == 2
    assert confirmed.approvals[0].reviewed_by == "engineer"
    assert service.get("project-1", revision=1).approvals == []


def test_unresolved_blocks_human_confirmation():
    service = EngineeringStateService()
    state = EngineeringState.model_validate(state_payload(unresolved=[{
        "id": "u-1", "description": traced("材料未知", "needs_review")
    }]))
    service.put(state, expected_revision=0)
    with pytest.raises(EngineeringStateGateError, match="unresolved"):
        service.confirm(
            "project-1",
            expected_revision=1,
            reviewed_by="engineer",
            subject="engineering_state",
            evidence=[EvidenceRef.model_validate(EVIDENCE)],
        )


def test_artifact_registry_enforces_provenance_revision_and_identity():
    with pytest.raises(ValidationError, match="concept_mesh"):
        Artifact.model_validate(artifact_payload(fidelity="concept_mesh"))

    service = EngineeringStateService()
    service.put(EngineeringState.model_validate(state_payload()), expected_revision=0)
    artifact = Artifact.model_validate(artifact_payload())
    service.register_artifact("project-1", artifact, expected_revision=1)
    assert service.get_artifact("project-1", "cad-1").content_hash == "a" * 64
    assert service.artifacts("project-1").artifacts == [artifact]

    with pytest.raises(EngineeringStateConflictError, match="已存在"):
        service.register_artifact("project-1", artifact, expected_revision=1)
    with pytest.raises(EngineeringStateConflictError, match="input_revision"):
        service.register_artifact(
            "project-1",
            Artifact.model_validate(artifact_payload(id="cad-2", input_revision=2)),
            expected_revision=1,
        )


def test_api_registered_query_confirm_and_artifact_flow():
    service = EngineeringStateService()
    app.dependency_overrides[get_engineering_state_service] = lambda: service
    client = TestClient(app)
    try:
        created = client.put("/api/v1/engineering-projects/project-1/state", json={
            "expected_revision": 0,
            "state": state_payload(),
        })
        assert created.status_code == 200
        assert client.get("/api/v1/engineering-projects/project-1/state?revision=1").status_code == 200

        stale = client.put("/api/v1/engineering-projects/project-1/state", json={
            "expected_revision": 0,
            "state": state_payload(),
        })
        assert stale.status_code == 409

        registered = client.post("/api/v1/engineering-projects/project-1/artifacts", json={
            "expected_revision": 1,
            "artifact": artifact_payload(),
        })
        assert registered.status_code == 201
        assert client.get("/api/v1/engineering-projects/project-1/artifacts").json()["artifacts"][0]["id"] == "cad-1"

        confirmed = client.post("/api/v1/engineering-projects/project-1/confirm", json={
            "expected_revision": 1,
            "reviewed_by": "api-engineer",
            "evidence": [EVIDENCE],
        })
        assert confirmed.status_code == 200
        assert confirmed.json()["revision"] == 2
    finally:
        app.dependency_overrides.clear()
