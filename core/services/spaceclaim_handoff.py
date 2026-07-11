"""SpaceClaim 几何交接编译器（特性一 · F1-P0-3，OQ4）。

新建编译器，直接由 ``EngineeringState`` → ``SpaceClaimHandoffContract``。
**不走** ``SimulationContractCompiler`` 的 approved / confirmed 门（几何交接
不需仿真审批）；``approval_status`` 由契约模型常量强制 ``"approved"``。

关键裁定落实：
* OQ3：分瓣角 ``segment_angle_deg`` 推导不出默认 360；翅片默认
  ``count=12, height_mm=8, thickness_mm=1.0, pitch_deg=30``。
* OQ5：每个 ``Material`` → ``MaterialProperties``（8 字段），缺字段用知识库
  默认材质表补（``BldcDefaults.default_material_properties``）。
* OQ4：派生 ``named_selections``（每关节 shell/load 各一）、``contacts``
  （相邻壳 bonded，单关节时为空）、``output_plan``。
"""
from __future__ import annotations

from core.knowledge.defaults import BldcDefaults, MATERIAL_PROPERTY_KEYS
from core.models.engineering_state import EngineeringState, Material
from core.models.simulation_contract import (
    Contact,
    CoordinateSystem,
    FinParameters,
    JointParameters,
    MaterialProperties,
    NamedSelection,
    UnitSystem,
)
from core.models.spaceclaim_contract import (
    SpaceClaimComponent,
    SpaceClaimHandoffContract,
    SpaceClaimOutputPlan,
)

DEFAULT_SEGMENT_ANGLE_DEG = 360.0
DEFAULT_FIN_COUNT = 12
DEFAULT_FIN_HEIGHT_MM = 8.0
DEFAULT_FIN_THICKNESS_MM = 1.0
DEFAULT_FIN_PITCH_DEG = 30.0


class SpaceClaimHandoffCompiler:
    """EngineeringState → SpaceClaimHandoffContract（几何交接，跳过仿真审批）。"""

    def compile(self, state: EngineeringState) -> SpaceClaimHandoffContract:
        joints = [self._joint_parameters(joint) for joint in state.joints]
        materials = [self._material_properties(material) for material in state.materials] or [
            self._material_properties_fallback()
        ]
        components = self._components(state)
        named_selections = self._named_selections(state)
        contacts = self._contacts(state)
        output_plan = self._output_plan(state)

        units = UnitSystem(
            length=state.units.length.value,
            angle=state.units.angle.value,
            temperature=state.units.temperature.value,
            power=state.units.power.value,
            pressure="Pa",
            stress="Pa",
        )
        coordinate_system = CoordinateSystem(
            handedness=state.coordinate_system.handedness.value,
            up_axis=state.coordinate_system.up_axis.value,
            origin_mm=state.coordinate_system.origin_mm.value,
        )
        return SpaceClaimHandoffContract(
            id="spaceclaim-handoff",
            project_id=state.project_id,
            engineering_revision=state.revision,
            units=units,
            coordinate_system=coordinate_system,
            joints=joints,
            components=components,
            interfaces=[],
            materials=materials,
            named_selections=named_selections,
            contacts=contacts,
            output_plan=output_plan,
        )

    # ----- joints -----

    def _joint_parameters(self, joint) -> JointParameters:
        return JointParameters(
            id=joint.id,
            outer_radius_mm=joint.outer_radius_mm.value,
            inner_radius_mm=joint.inner_radius_mm.value,
            axial_length_mm=joint.axial_length_mm.value,
            segment_angle_deg=DEFAULT_SEGMENT_ANGLE_DEG,
            shell_wall_thickness_mm=joint.shell_wall_thickness_mm.value,
            axis=joint.axis.value,
            fins=FinParameters(
                count=DEFAULT_FIN_COUNT,
                height_mm=DEFAULT_FIN_HEIGHT_MM,
                thickness_mm=DEFAULT_FIN_THICKNESS_MM,
                pitch_deg=DEFAULT_FIN_PITCH_DEG,
            ),
        )

    # ----- materials（OQ5 补缺）-----

    def _material_properties(self, material: Material) -> MaterialProperties:
        props = dict(material.properties)
        try:
            defaults = BldcDefaults.default_material_properties(material.id)
        except KeyError:
            defaults = BldcDefaults.default_material_properties("al")
        filled: dict[str, float] = {}
        for key in MATERIAL_PROPERTY_KEYS:
            ev = props.get(key)
            if ev is not None and ev.value is not None:
                filled[key] = float(ev.value)
            else:
                filled[key] = float(defaults[key])
        return MaterialProperties(
            material_id=material.id,
            name=material.name.value,
            density_kg_m3=filled["density_kg_m3"],
            thermal_conductivity_w_mk=filled["thermal_conductivity_w_mk"],
            specific_heat_j_kgk=filled["specific_heat_j_kgk"],
            coefficient_thermal_expansion_1_k=filled["coefficient_thermal_expansion_1_k"],
            youngs_modulus_pa=filled["youngs_modulus_pa"],
            poissons_ratio=filled["poissons_ratio"],
            yield_strength_pa=filled["yield_strength_pa"],
            ultimate_tensile_strength_pa=filled["ultimate_tensile_strength_pa"],
        )

    def _material_properties_fallback(self) -> MaterialProperties:
        defaults = BldcDefaults.default_material_properties("al")
        return MaterialProperties(
            material_id="al",
            name="Aluminum",
            density_kg_m3=defaults["density_kg_m3"],
            thermal_conductivity_w_mk=defaults["thermal_conductivity_w_mk"],
            specific_heat_j_kgk=defaults["specific_heat_j_kgk"],
            coefficient_thermal_expansion_1_k=defaults["coefficient_thermal_expansion_1_k"],
            youngs_modulus_pa=defaults["youngs_modulus_pa"],
            poissons_ratio=defaults["poissons_ratio"],
            yield_strength_pa=defaults["yield_strength_pa"],
            ultimate_tensile_strength_pa=defaults["ultimate_tensile_strength_pa"],
        )

    # ----- components / selections / contacts / output -----

    def _components(self, state: EngineeringState) -> list[SpaceClaimComponent]:
        material_id = state.materials[0].id if state.materials else "al"
        if state.joints:
            return [SpaceClaimComponent(id=joint.id, material_id=material_id) for joint in state.joints]
        return [SpaceClaimComponent(id="shell", material_id=material_id)]

    def _named_selections(self, state: EngineeringState) -> list[NamedSelection]:
        selections: list[NamedSelection] = []
        for joint in state.joints:
            selections.append(
                NamedSelection(name=f"{joint.id}-shell", purpose="solid", entity_type="body")
            )
            selections.append(
                NamedSelection(name=f"{joint.id}-load", purpose="load", entity_type="face")
            )
        if not selections:
            selections.append(NamedSelection(name="shell", purpose="solid", entity_type="body"))
        return selections

    def _contacts(self, state: EngineeringState) -> list[Contact]:
        contacts: list[Contact] = []
        joints = state.joints
        for i in range(len(joints) - 1):
            contacts.append(
                Contact(
                    id=f"contact-{joints[i].id}-{joints[i + 1].id}",
                    source_named_selection=f"{joints[i].id}-shell",
                    target_named_selection=f"{joints[i + 1].id}-shell",
                    contact_type="bonded",
                )
            )
        return contacts

    def _output_plan(self, state: EngineeringState) -> SpaceClaimOutputPlan:
        return SpaceClaimOutputPlan(workspace_uri=f"file:///isolated/{state.project_id}")
