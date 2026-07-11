"""
Exploded view data models for 3D model decomposition and part description.

Provides the contract between the OBJ parser, LLM description generator,
and the frontend exploded-view viewer.
"""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class PartCategory(str, Enum):
    MOTOR = "motor"
    STRUCTURAL = "structural"
    ELECTRONIC = "electronic"
    HOUSING = "housing"
    COOLING = "cooling"
    FASTENER = "fastener"
    CABLE = "cable"
    SENSOR = "sensor"
    JOINT = "joint"
    GRIPPER = "gripper"
    UNKNOWN = "unknown"


class PartGeometryInfo(BaseModel):
    """Geometric metadata extracted from the OBJ file for a single part."""
    vertex_count: int = Field(..., description="Number of vertices in this part")
    face_count: int = Field(..., description="Number of triangular faces")
    bounding_box_min: list[float] = Field(..., description="Min corner [x, y, z]")
    bounding_box_max: list[float] = Field(..., description="Max corner [x, y, z]")
    centroid: list[float] = Field(..., description="Center point [x, y, z]")
    size: list[float] = Field(..., description="Dimensions [dx, dy, dz]")
    volume_estimate: float = Field(0.0, description="Approximate volume (bounding box)")
    dominant_axis: str = Field("y", description="Dominant elongation axis")


class ExplodedPart(BaseModel):
    """A single decomposed part with metadata and classification."""
    part_id: str = Field(..., description="Stable identifier, e.g. 'part-01'")
    obj_name: str = Field(..., description="Original 'o' name from OBJ file")
    display_name: str = Field(..., description="Human-readable name")
    category: PartCategory = Field(..., description="Classified category")
    geometry: PartGeometryInfo
    classification_reason: str = Field("", description="Why this category was chosen")
    sort_order: int = Field(0, description="Display order")


class PartDescription(BaseModel):
    """LLM-generated description for a single part."""
    part_id: str
    category: PartCategory
    title: str = Field(..., description="Part title, e.g. '基座电机 IKI1602'")
    subtitle: str = Field("", description="One-line subtitle")
    model_number: Optional[str] = Field(None, description="Model number for motors/chips")
    summary: str = Field(..., description="Brief one-sentence summary")
    description: str = Field(..., description="Detailed multi-paragraph description")
    design_rationale: Optional[str] = Field(None, description="For structural parts: why this design")
    specifications: dict[str, str] = Field(default_factory=dict, description="Key specs as key-value")
    aesthetic_notes: Optional[str] = Field(None, description="For housing/structural: aesthetic analysis")
    material: Optional[str] = Field(None, description="Likely material")


class ExplodedViewResult(BaseModel):
    """Complete result: parts metadata + descriptions."""
    model_id: str
    model_name: str
    source_file: str
    total_parts: int
    parts: list[ExplodedPart]
    descriptions: list[PartDescription] = Field(default_factory=list)


class ParseObjRequest(BaseModel):
    """Request to parse an OBJ file."""
    obj_path: str = Field(..., description="Absolute path to the .obj file")
    model_name: str = Field("robot-arm", description="Display name for the model")


class DescribePartsRequest(BaseModel):
    """Request to generate LLM descriptions for parts."""
    parts: list[ExplodedPart]
    model_context: str = Field(
        "六轴机械臂，使用 IKI1602 系列伺服电机",
        description="Context about the model for the LLM",
    )
