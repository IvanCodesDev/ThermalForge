from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from core.api.app import app
from core.api.routes.agent_pipeline import (
    get_agent_pipeline_runtime,
    get_specification_extraction_service,
)
from core.models.agent_pipeline import (
    CreatePipelineRequest,
    EngineeringSpecification,
    PipelineArtifact,
    PipelineState,
    RegisterHyper3DResultRequest,
    SourceAsset,
    SourceKind,
    ValidationReport,
)
from core.config import Settings
from core.services.agent_pipeline import (
    AgentPipelineRuntime,
    PipelineConflictError,
    PipelineGateError,
    SpecificationExtractionService,
)


def source() -> SourceAsset:
    return SourceAsset(id="datasheet-1", kind=SourceKind.DATASHEET, uri="file:///datasheet.pdf", filename="datasheet.pdf")


def spec() -> EngineeringSpecification:
    return EngineeringSpecification(product_name="FOC 机械臂关节", overall_bbox_mm=(160, 140, 110))


def proxy_artifacts() -> list[PipelineArtifact]:
    return [
        PipelineArtifact(id="proxy", role="engineering_glb", uri="file:///proxy.glb", provider="cadquery", fidelity="engineering_proxy"),
        PipelineArtifact(id="render", role="reference_render", uri="file:///render.png", provider="cadquery", fidelity="engineering_proxy"),
    ]


def prepared_runtime() -> tuple[AgentPipelineRuntime, object]:
    runtime = AgentPipelineRuntime()
    pipeline = runtime.create(CreatePipelineRequest(product_name="FOC 机械臂关节", sources=[source()]))
    proposed = runtime.propose_specification(pipeline.id, spec())
    runtime.review_specification(pipeline.id, accepted=True, reviewed_by="engineer", expected_revision=proposed.revision)
    return runtime, pipeline.id


def test_human_gate_and_revision_conflict():
    runtime = AgentPipelineRuntime()
    pipeline = runtime.create(CreatePipelineRequest(product_name="关节", sources=[source()]))
    with pytest.raises(PipelineGateError):
        runtime.register_geometry(pipeline.id, proxy_artifacts())

    proposed = runtime.propose_specification(pipeline.id, spec())
    with pytest.raises(PipelineConflictError):
        runtime.review_specification(pipeline.id, accepted=True, reviewed_by="engineer", expected_revision=proposed.revision - 1)


def test_geometry_requires_engineering_proxy_and_reference_render_for_compile():
    runtime, pipeline_id = prepared_runtime()
    with pytest.raises(PipelineGateError, match="engineering_proxy"):
        runtime.register_geometry(pipeline_id, [
            PipelineArtifact(id="source", role="engineering_glb", uri="file:///source.glb", provider="step", fidelity="source")
        ])

    runtime.register_geometry(pipeline_id, [
        PipelineArtifact(id="proxy", role="engineering_glb", uri="file:///proxy.glb", provider="cadquery", fidelity="engineering_proxy")
    ])
    with pytest.raises(PipelineGateError, match="参考图"):
        runtime.compile_hyper3d(pipeline_id)


def test_hyper3d_uuid_and_concept_mesh_provenance():
    runtime, pipeline_id = prepared_runtime()
    runtime.register_geometry(pipeline_id, proxy_artifacts())
    runtime.compile_hyper3d(pipeline_id)
    runtime.mark_hyper3d_submitted(pipeline_id, "task-1")

    with pytest.raises(PipelineGateError, match="UUID"):
        runtime.register_hyper3d_result(pipeline_id, "task-2", [
            PipelineArtifact(id="mesh", role="hyper3d_glb", uri="file:///mesh.glb", provider="hyper3d", fidelity="concept_mesh", task_uuid="task-2")
        ])
    with pytest.raises(ValidationError, match="task UUID"):
        RegisterHyper3DResultRequest(task_uuid="task-1", artifacts=[
            PipelineArtifact(id="mesh", role="hyper3d_glb", uri="file:///mesh.glb", provider="hyper3d", fidelity="concept_mesh", task_uuid="other")
        ])
    with pytest.raises(ValidationError, match="来源"):
        RegisterHyper3DResultRequest(task_uuid="task-1", artifacts=[
            PipelineArtifact(id="mesh", role="hyper3d_glb", uri="file:///mesh.glb", provider="local", fidelity="concept_mesh", task_uuid="task-1")
        ])


def test_validation_completion_status_and_manifest():
    runtime, pipeline_id = prepared_runtime()
    runtime.register_geometry(pipeline_id, proxy_artifacts())
    runtime.compile_hyper3d(pipeline_id)
    runtime.mark_hyper3d_submitted(pipeline_id, "task-1")
    runtime.register_hyper3d_result(pipeline_id, "task-1", [
        PipelineArtifact(id="mesh", role="hyper3d_glb", uri="file:///mesh.glb", provider="hyper3d", fidelity="concept_mesh", task_uuid="task-1")
    ])
    completed = runtime.submit_validation(pipeline_id, ValidationReport(passed=True))

    assert completed.state == PipelineState.COMPLETED
    assert runtime.status(pipeline_id).validation_passed is True
    manifest = runtime.frontend_manifest(pipeline_id)
    assert manifest.engineering_proxy
    assert manifest.reference_renders
    assert manifest.concept_meshes[0].task_uuid == "task-1"
    assert "不是可制造 CAD" in manifest.disclaimer


def test_specification_extraction_uses_configured_model_and_records_audit_event():
    class MockOpenAIClient:
        def __init__(self):
            self.call = None

        async def create_response(self, **kwargs):
            self.call = kwargs
            return {"output_text": __import__("json").dumps({
                "specification": {
                    "product_name": "FOC 机械臂关节",
                    "overall_bbox_mm": [160, 140, 110],
                    "components": [],
                    "interfaces": [],
                    "assumptions": [],
                    "unresolved": ["电机材料未知"],
                },
                "component_semantic_candidates": [],
            }, ensure_ascii=False)}

    settings = Settings(OPENAI_TEXT_MODEL="gpt-5.6-sol")
    mock_client = MockOpenAIClient()
    service = SpecificationExtractionService(settings, mock_client)
    runtime = AgentPipelineRuntime()
    app.dependency_overrides[get_agent_pipeline_runtime] = lambda: runtime
    app.dependency_overrides[get_specification_extraction_service] = lambda: service
    client = TestClient(app)
    try:
        created = client.post("/api/v1/agent-pipelines", json={
            "product_name": "FOC 机械臂关节",
            "sources": [source().model_dump(mode="json")],
        }).json()
        response = client.post(
            f"/api/v1/agent-pipelines/{created['id']}/specification/extract",
            json={"source_contents": {"datasheet-1": "外形尺寸 160 x 140 x 110 mm"}},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert mock_client.call["model"] == "gpt-5.6-sol"
    assert service.settings.openai_text_model == "gpt-5.6-sol"
    assert mock_client.call["metadata"]["purpose"] == "engineering_specification_extraction"
    event = response.json()["events"][-1]
    assert event["agent"] == "specification_agent"
    assert event["agent_version"] == "1.0.0"
    assert event["prompt_id"] == "specification_extraction.v1"
    assert len(event["prompt_hash"]) == 64
    assert event["model"] == "gpt-5.6-sol"
    assert event["skills"] == ["specification_extraction"]
    assert event["tools"] == ["source_content_reader"]
    assert event["detail"] == {
        "provider": "openai",
        "purpose": "engineering_specification_extraction",
        "unresolved": ["电机材料未知"],
    }


def test_agent_pipeline_api_end_to_end_without_external_api():
    runtime = AgentPipelineRuntime()
    app.dependency_overrides[get_agent_pipeline_runtime] = lambda: runtime
    client = TestClient(app)
    try:
        created = client.post("/api/v1/agent-pipelines", json={
            "product_name": "FOC 机械臂关节",
            "sources": [source().model_dump(mode="json")],
        })
        assert created.status_code == 201
        pipeline = created.json()

        blocked = client.post(f"/api/v1/agent-pipelines/{pipeline['id']}/geometry", json={"artifacts": [item.model_dump(mode="json") for item in proxy_artifacts()]})
        assert blocked.status_code == 409

        proposed = client.post(f"/api/v1/agent-pipelines/{pipeline['id']}/specification", json={"specification": spec().model_dump(mode="json")})
        reviewed = client.post(f"/api/v1/agent-pipelines/{pipeline['id']}/specification/review", json={
            "accepted": True, "reviewed_by": "api-user", "expected_revision": proposed.json()["revision"]
        })
        assert reviewed.status_code == 200
        assert client.post(f"/api/v1/agent-pipelines/{pipeline['id']}/geometry", json={"artifacts": [item.model_dump(mode="json") for item in proxy_artifacts()]}).status_code == 200
        assert client.post(f"/api/v1/agent-pipelines/{pipeline['id']}/hyper3d/compile").status_code == 200
        assert client.post(f"/api/v1/agent-pipelines/{pipeline['id']}/hyper3d/submitted", json={"task_uuid": "task-api"}).status_code == 200
        result = client.post(f"/api/v1/agent-pipelines/{pipeline['id']}/hyper3d/result", json={
            "task_uuid": "task-api",
            "artifacts": [{"id": "mesh", "role": "hyper3d_glb", "uri": "file:///mesh.glb", "provider": "hyper3d", "fidelity": "concept_mesh", "task_uuid": "task-api"}],
        })
        assert result.status_code == 200
        assert client.post(f"/api/v1/agent-pipelines/{pipeline['id']}/validation", json={"passed": True}).json()["state"] == "completed"
        assert client.get(f"/api/v1/agent-pipelines/{pipeline['id']}/status").json()["validation_passed"] is True
        assert client.get(f"/api/v1/agent-pipelines/{pipeline['id']}/manifest").json()["concept_meshes"][0]["task_uuid"] == "task-api"
    finally:
        app.dependency_overrides.clear()
