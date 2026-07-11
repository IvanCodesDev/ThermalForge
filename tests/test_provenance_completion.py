from uuid import uuid4

import pytest

from core.services.provenance import (
    ProvenanceCompletionEvidence,
    ProvenanceCompletionGate,
    ProvenanceGateError,
)
from core.models.agent_pipeline import CreatePipelineRequest, PipelineArtifact, PipelineState, ValidationReport
from core.services.agent_pipeline import AgentPipelineRuntime, PipelineGateError
from tests.test_agent_pipeline import proxy_artifacts, source, spec


def complete_evidence() -> ProvenanceCompletionEvidence:
    return ProvenanceCompletionEvidence(
        pipeline_id=uuid4(), pipeline_revision=7,
        source_artifact_hashes=("a" * 64,),
        specification_execution_id=uuid4(), specification_execution_status="succeeded",
        human_confirmation_revision=2,
        geometry_artifact_id="spaceclaim-step", geometry_content_hash="b" * 64,
        geometry_check_report_hash="c" * 64,
        hyper3d_root_task_uuid="root-task-1",
        hyper3d_asset_id="hyper3d-glb", hyper3d_asset_hash="d" * 64,
        simulation_handoff_id="handoff-1", simulation_result_hash="e" * 64,
        acceptance_status="passed",
    )


def test_complete_provenance_produces_stable_chain_digest() -> None:
    evidence = complete_evidence()
    first = ProvenanceCompletionGate().evaluate(evidence)
    second = ProvenanceCompletionGate().evaluate(evidence)
    assert first.eligible is True
    assert first.chain_hash == second.chain_hash
    assert len(first.chain_hash) == 64


def test_provenance_gate_fails_closed_when_source_hash_is_missing() -> None:
    evidence = complete_evidence().model_copy(update={"source_artifact_hashes": ()})
    with pytest.raises(ProvenanceGateError, match="source artifact"):
        ProvenanceCompletionGate().evaluate(evidence)


def test_provenance_gate_rejects_nonpassing_server_acceptance() -> None:
    evidence = complete_evidence().model_copy(update={"acceptance_status": "review_required"})
    with pytest.raises(ProvenanceGateError, match="acceptance"):
        ProvenanceCompletionGate().evaluate(evidence)


def test_pipeline_completion_accepts_only_matching_provenance_report() -> None:
    runtime = AgentPipelineRuntime()
    pipeline = runtime.create(CreatePipelineRequest(product_name="FOC arm", sources=[source()]))
    proposed = runtime.propose_specification(pipeline.id, spec())
    runtime.review_specification(pipeline.id, accepted=True, reviewed_by="engineer", expected_revision=proposed.revision)
    runtime.register_geometry(pipeline.id, proxy_artifacts())
    runtime.compile_hyper3d(pipeline.id)
    runtime.mark_hyper3d_submitted(pipeline.id, "task-1")
    ready = runtime.register_hyper3d_result(pipeline.id, "task-1", [
        PipelineArtifact(id="mesh", role="hyper3d_glb", uri="file:///mesh.glb", provider="hyper3d",
                         fidelity="concept_mesh", task_uuid="task-1")
    ])
    evidence = complete_evidence().model_copy(update={
        "pipeline_id": pipeline.id, "pipeline_revision": ready.revision
    })
    report = ProvenanceCompletionGate().evaluate(evidence)

    completed = runtime.complete_with_provenance(pipeline.id, report)
    assert completed.state == PipelineState.COMPLETED
    assert completed.validation == ValidationReport(passed=True, findings=[f"provenance:{report.chain_hash}"])

    with pytest.raises(PipelineGateError):
        runtime.complete_with_provenance(pipeline.id, report.model_copy(update={"pipeline_revision": 999}))
