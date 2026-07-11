"""Contracts for governed FOC robotic-arm multi-view image prompts."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictPromptModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FocArmMultiviewPromptRequest(StrictPromptModel):
    target_product: str
    dof: Literal[4]
    image_model: Literal["gpt-image-2"]
    reconstruction_target: Literal["Hyper3D Rodin Gen-2"]
    required_views: list[str]
    visual_priority: str
    source_snapshot: dict[str, Any]


class FocArmViewPrompt(StrictPromptModel):
    id: Literal["mother_three_quarter", "front", "left", "rear", "top", "elbow_section"]
    camera: str = Field(min_length=20)
    purpose: str = Field(min_length=20)
    prompt: str = Field(min_length=300)


class FocArmImageSettings(StrictPromptModel):
    model: Literal["gpt-image-2"]
    size: str
    quality: Literal["high"]
    output_format: Literal["png"]
    background: Literal["opaque"]


class FocArmMultiviewPromptOutput(StrictPromptModel):
    design_name: str = Field(min_length=3)
    source_facts: list[str] = Field(min_length=8)
    concept_assumptions: list[str] = Field(min_length=3)
    shared_identity: str = Field(min_length=300)
    views: list[FocArmViewPrompt] = Field(min_length=6, max_length=6)
    negative_prompt: str = Field(min_length=200)
    image_settings: FocArmImageSettings
    hyper3d_guidance: list[str] = Field(min_length=4)
    fidelity_notice: str = Field(min_length=80)

    @model_validator(mode="after")
    def require_all_views(self) -> "FocArmMultiviewPromptOutput":
        required = {"mother_three_quarter", "front", "left", "rear", "top", "elbow_section"}
        actual = {view.id for view in self.views}
        if actual != required:
            raise ValueError(f"views must contain exactly {sorted(required)}")
        return self
