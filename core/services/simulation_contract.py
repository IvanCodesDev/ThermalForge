"""EngineeringState 到仿真交接契约的编译及结果摄取。"""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from core.models.engineering_state import Artifact, ArtifactFidelity, EngineeringState, TracedValue, ValueStatus
from core.models.simulation_contract import AcceptanceViolation, ResultAcceptance, SimulationHandoffContract, SimulationResultContract


class SimulationContractError(ValueError):
    pass


_REQUIRED_MATERIAL_PROPERTIES = {
    "density_kg_m3",
    "thermal_conductivity_w_mk",
    "specific_heat_j_kgk",
    "coefficient_thermal_expansion_1_k",
    "youngs_modulus_pa",
    "poissons_ratio",
    "yield_strength_pa",
    "ultimate_tensile_strength_pa",
}


class SimulationContractCompiler:
    """只编译经过人工批准、关键值全部确认的工程状态。"""

    def compile(
        self,
        state: EngineeringState,
        *,
        geometry_artifact: Artifact,
        created_by: str,
        model: str,
        joint_extensions: dict[str, dict[str, Any]],
        named_selections: list[dict[str, Any]],
        contacts: list[dict[str, Any]],
        mesh_plan: dict[str, Any],
        solver_plan: dict[str, Any],
        acceptance: dict[str, Any],
        api_version: str = "V251",
    ) -> SimulationHandoffContract:
        self._require_approved(state)
        self._require_confirmed_state(state)
        self._require_geometry(state, geometry_artifact)
        if not named_selections:
            raise SimulationContractError("Named Selection 不能为空")

        selection_names = {item.get("name") for item in named_selections}
        if None in selection_names or len(selection_names) != len(named_selections):
            raise SimulationContractError("Named Selection 名称必须存在且唯一")

        materials = []
        for material in state.materials:
            missing = _REQUIRED_MATERIAL_PROPERTIES - material.properties.keys()
            if missing:
                raise SimulationContractError(
                    f"材料 {material.id} 缺少属性: {', '.join(sorted(missing))}"
                )
            materials.append({
                "material_id": material.id,
                "name": material.name.value,
                **{key: material.properties[key].value for key in _REQUIRED_MATERIAL_PROPERTIES},
            })

        joints = []
        for joint in state.joints:
            extension = joint_extensions.get(joint.id)
            if extension is None:
                raise SimulationContractError(f"关节 {joint.id} 缺少分瓣角/翅片确认参数")
            joints.append({
                "id": joint.id,
                "outer_radius_mm": joint.outer_radius_mm.value,
                "inner_radius_mm": joint.inner_radius_mm.value,
                "axial_length_mm": joint.axial_length_mm.value,
                "shell_wall_thickness_mm": joint.shell_wall_thickness_mm.value,
                "axis": joint.axis.value,
                **extension,
            })

        loads = [{
            "id": load.id,
            "named_selection": load.component_id.value,
            "load_type": "heat_power",
            "magnitude": load.heat_w.value,
            "unit": "W",
        } for load in state.thermal_loads]
        cases = [{
            "id": case.id,
            "ambient_temperature_c": case.ambient_temperature_c.value,
            "thermal_load_ids": case.thermal_load_ids.value,
        } for case in state.operating_cases]
        referenced = {load["named_selection"] for load in loads}
        referenced.update(contact[key] for contact in contacts for key in (
            "source_named_selection", "target_named_selection"
        ))
        missing_selections = referenced - selection_names
        if missing_selections:
            raise SimulationContractError(
                "缺少 Named Selection: " + ", ".join(sorted(missing_selections))
            )

        try:
            return SimulationHandoffContract.model_validate({
                "schema": "thermalforge.simulation_handoff",
                "version": "1.0.0",
                "project_id": state.project_id,
                "engineering_revision": state.revision,
                "created_by": created_by,
                "model": model,
                "approval_status": "approved",
                "units": {
                    "length": state.units.length.value,
                    "angle": state.units.angle.value,
                    "temperature": state.units.temperature.value,
                    "power": state.units.power.value,
                    "pressure": "Pa",
                    "stress": "Pa",
                },
                "coordinate_system": {
                    "handedness": state.coordinate_system.handedness.value,
                    "up_axis": state.coordinate_system.up_axis.value,
                    "origin_mm": state.coordinate_system.origin_mm.value,
                },
                "geometry_generator": {
                    "provider": "spaceclaim",
                    "api_version": api_version,
                    "script_uri": geometry_artifact.metadata.get("script_uri", geometry_artifact.uri),
                    "output_geometry_uri": geometry_artifact.uri,
                    "artifact_id": geometry_artifact.id,
                    "fidelity": geometry_artifact.fidelity.value,
                },
                "joints": joints,
                "materials": materials,
                "thermal_loads": loads,
                "contacts": contacts,
                "operating_cases": cases,
                "named_selections": named_selections,
                "mesh_plan": mesh_plan,
                "solver_plan": solver_plan,
                "acceptance": acceptance,
            })
        except ValidationError as exc:
            raise SimulationContractError(f"仿真交接契约无效: {exc}") from exc

    @staticmethod
    def _require_approved(state: EngineeringState) -> None:
        if state.unresolved:
            raise SimulationContractError("EngineeringState 仍有 unresolved 项")
        if not any(
            approval.decision == "approved" and approval.subject == "engineering_state"
            for approval in state.approvals
        ):
            raise SimulationContractError("EngineeringState 未授权批准")

    @classmethod
    def _require_confirmed_state(cls, state: EngineeringState) -> None:
        values: list[tuple[str, TracedValue[Any]]] = [
            ("units.length", state.units.length),
            ("units.angle", state.units.angle),
            ("units.temperature", state.units.temperature),
            ("units.power", state.units.power),
            ("coordinate_system.handedness", state.coordinate_system.handedness),
            ("coordinate_system.up_axis", state.coordinate_system.up_axis),
            ("coordinate_system.origin_mm", state.coordinate_system.origin_mm),
        ]
        for joint in state.joints:
            for field in ("axis", "outer_radius_mm", "inner_radius_mm", "axial_length_mm", "shell_wall_thickness_mm"):
                values.append((f"joint.{joint.id}.{field}", getattr(joint, field)))
        for material in state.materials:
            values.append((f"material.{material.id}.name", material.name))
            for key, prop in material.properties.items():
                if key in _REQUIRED_MATERIAL_PROPERTIES:
                    if prop.status != "confirmed" or not prop.evidence:
                        raise SimulationContractError(f"关键值 material.{material.id}.{key} 未确认")
        for load in state.thermal_loads:
            values.extend([(f"load.{load.id}.component_id", load.component_id), (f"load.{load.id}.heat_w", load.heat_w)])
        for case in state.operating_cases:
            values.extend([
                (f"case.{case.id}.ambient_temperature_c", case.ambient_temperature_c),
                (f"case.{case.id}.thermal_load_ids", case.thermal_load_ids),
            ])
        unconfirmed = [name for name, value in values if value.status != ValueStatus.CONFIRMED]
        if unconfirmed:
            raise SimulationContractError("关键值未确认: " + ", ".join(unconfirmed))

    @staticmethod
    def _require_geometry(state: EngineeringState, artifact: Artifact) -> None:
        if artifact.input_revision != state.revision:
            raise SimulationContractError("仿真几何 revision 与 EngineeringState 不一致")
        if artifact.fidelity == ArtifactFidelity.CONCEPT_MESH:
            raise SimulationContractError("concept_mesh 不能作为仿真几何")
        if artifact.fidelity not in {ArtifactFidelity.ENGINEERING_PROXY, ArtifactFidelity.MANUFACTURING_CAD}:
            raise SimulationContractError("工件不是可用仿真几何")


class SimulationResultIngestor:
    def ingest(
        self,
        payload: dict[str, Any] | SimulationResultContract,
        handoff: SimulationHandoffContract,
    ) -> SimulationResultContract:
        try:
            result = payload if isinstance(payload, SimulationResultContract) else SimulationResultContract.model_validate(payload, strict=False)
        except ValidationError as exc:
            raise SimulationContractError(f"仿真结果契约无效: {exc}") from exc
        if result.project_id != handoff.project_id or result.engineering_revision != handoff.engineering_revision:
            raise SimulationContractError("结果与 handoff 工程身份不一致")
        if result.model != handoff.model:
            raise SimulationContractError("结果模型类型与 handoff 不一致")
        expected_cases = {case.id for case in handoff.operating_cases}
        actual_cases = {case.case_id for case in result.cases}
        if actual_cases != expected_cases:
            raise SimulationContractError("结果 case 集合与 handoff 不一致")
        for case in result.cases:
            if handoff.acceptance.require_converged and not case.converged:
                raise SimulationContractError(f"case {case.case_id} 未收敛")
            if case.max_temperature_c > handoff.acceptance.max_temperature_c:
                raise SimulationContractError(f"case {case.case_id} 超过最高温度验收值")
            if handoff.acceptance.max_pressure_drop_pa is not None and (
                case.pressure_drop_pa is None or case.pressure_drop_pa > handoff.acceptance.max_pressure_drop_pa
            ):
                raise SimulationContractError(f"case {case.case_id} 未通过压降验收")
            if handoff.acceptance.min_safety_factor is not None and (
                case.min_safety_factor is None or case.min_safety_factor < handoff.acceptance.min_safety_factor
            ):
                raise SimulationContractError(f"case {case.case_id} 未通过安全系数验收")
        return result

    def validate_identity(self, result: SimulationResultContract, handoff_id: str, handoff: SimulationHandoffContract) -> None:
        if result.handoff_id != handoff_id:
            raise SimulationContractError("结果 handoff_id 不匹配")
        if result.project_id != handoff.project_id or result.engineering_revision != handoff.engineering_revision:
            raise SimulationContractError("结果与 handoff 工程身份不一致")
        if result.model != handoff.model or result.solver != handoff.solver_plan.solver:
            raise SimulationContractError("结果模型或 solver 与 handoff 不一致")
        if {case.case_id for case in result.cases} != {case.id for case in handoff.operating_cases}:
            raise SimulationContractError("结果 case 集合与 handoff 不一致")

    def evaluate_acceptance(self, result: SimulationResultContract, handoff: SimulationHandoffContract) -> ResultAcceptance:
        violations: list[AcceptanceViolation] = []
        for case in result.cases:
            if handoff.acceptance.require_converged and not case.converged:
                violations.append(AcceptanceViolation(code="not_converged", case_id=case.case_id, message="求解未收敛"))
            if case.max_temperature_c > handoff.acceptance.max_temperature_c:
                violations.append(AcceptanceViolation(code="temperature_exceeded", case_id=case.case_id, message="超过最高温度验收值"))
            if handoff.acceptance.max_pressure_drop_pa is not None and (case.pressure_drop_pa is None or case.pressure_drop_pa > handoff.acceptance.max_pressure_drop_pa):
                violations.append(AcceptanceViolation(code="pressure_drop_failed", case_id=case.case_id, message="未通过压降验收"))
            if handoff.acceptance.min_safety_factor is not None and (case.min_safety_factor is None or case.min_safety_factor < handoff.acceptance.min_safety_factor):
                violations.append(AcceptanceViolation(code="safety_factor_failed", case_id=case.case_id, message="未通过安全系数验收"))
        return ResultAcceptance(status="review_required" if violations else "passed", violations=violations)
