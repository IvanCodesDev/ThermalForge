"""SpaceClaim.Api.V251 确定性几何交接契约。"""
from __future__ import annotations

from typing import Literal
from pydantic import Field, model_validator
from core.models.simulation_contract import CoordinateSystem, JointParameters, MaterialProperties, NamedSelection, UnitSystem, Contact
from core.models.simulation_contract import StrictModel

class SpaceClaimComponent(StrictModel):
    id: str = Field(min_length=1)
    material_id: str = Field(min_length=1)

class SpaceClaimInterface(StrictModel):
    id: str = Field(min_length=1)
    parent_component_id: str
    child_component_id: str

class SpaceClaimOutputPlan(StrictModel):
    workspace_uri: str = Field(min_length=1)
    geometry_formats: tuple[Literal["step", "scdoc"], ...] = ("step",)
    render_required: bool = True

class SpaceClaimHandoffContract(StrictModel):
    schema: Literal["thermalforge.spaceclaim_handoff"] = "thermalforge.spaceclaim_handoff"
    version: Literal["1.0.0"] = "1.0.0"
    id: str
    project_id: str
    engineering_revision: int = Field(ge=1)
    provider: Literal["spaceclaim"] = "spaceclaim"
    api_version: Literal["V251"] = "V251"
    approval_status: Literal["approved"] = "approved"
    units: UnitSystem
    coordinate_system: CoordinateSystem
    joints: list[JointParameters] = Field(min_length=1)
    components: list[SpaceClaimComponent] = Field(min_length=1)
    interfaces: list[SpaceClaimInterface] = Field(default_factory=list)
    materials: list[MaterialProperties] = Field(min_length=1)
    named_selections: list[NamedSelection] = Field(min_length=1)
    contacts: list[Contact] = Field(default_factory=list)
    output_plan: SpaceClaimOutputPlan

    @model_validator(mode="after")
    def validate_references(self) -> "SpaceClaimHandoffContract":
        names = [item.name for item in self.named_selections]
        if len(names) != len(set(names)):
            raise ValueError("Named Selection 名称必须唯一")
        known = set(names)
        for contact in self.contacts:
            if contact.source_named_selection not in known or contact.target_named_selection not in known:
                raise ValueError("contact 引用了未知 Named Selection")
        return self
