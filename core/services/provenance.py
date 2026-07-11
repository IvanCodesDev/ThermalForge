"""Fail-closed provenance gate for the sole production completion transition."""
from __future__ import annotations

import hashlib
import json
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ProvenanceGateError(PermissionError):
    pass


class ProvenanceCompletionEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_id: UUID
    pipeline_revision: int = Field(ge=1)
    source_artifact_hashes: tuple[str, ...]
    specification_execution_id: UUID
    specification_execution_status: Literal["started", "succeeded", "failed"]
    human_confirmation_revision: int = Field(ge=1)
    geometry_artifact_id: str = Field(min_length=1)
    geometry_content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    geometry_check_report_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    hyper3d_root_task_uuid: str = Field(min_length=1)
    hyper3d_asset_id: str = Field(min_length=1)
    hyper3d_asset_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    simulation_handoff_id: str = Field(min_length=1)
    simulation_result_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    acceptance_status: Literal["passed", "review_required"]


class ProvenanceCompletionReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    pipeline_id: UUID
    pipeline_revision: int
    eligible: Literal[True] = True
    chain_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProvenanceCompletionGate:
    """Validate every required link and commit a deterministic chain digest."""

    def evaluate(self, evidence: ProvenanceCompletionEvidence) -> ProvenanceCompletionReport:
        if not evidence.source_artifact_hashes:
            raise ProvenanceGateError("at least one hashed source artifact is required")
        if any(len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value)
               for value in evidence.source_artifact_hashes):
            raise ProvenanceGateError("source artifact hashes must be lowercase SHA-256")
        if evidence.specification_execution_status != "succeeded":
            raise ProvenanceGateError("specification extraction execution did not succeed")
        if evidence.acceptance_status != "passed":
            raise ProvenanceGateError("server-computed simulation acceptance did not pass")

        canonical = json.dumps(
            evidence.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return ProvenanceCompletionReport(
            pipeline_id=evidence.pipeline_id,
            pipeline_revision=evidence.pipeline_revision,
            chain_hash=hashlib.sha256(canonical).hexdigest(),
        )
