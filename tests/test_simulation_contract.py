from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.models.engineering_state import Artifact, EngineeringState
from core.models.simulation_contract import GeometryGenerator
from core.services.simulation_contract import (
    SimulationContractCompiler,
    SimulationContractError,
    SimulationResultIngestor,
)


EVIDENCE = {"source_id": "datasheet", "locator": "page:1"}


def traced(value, status="confirmed"):
    return {"value": value, "status": status, "evidence": [EVIDENCE]}


def property_value(value, unit):
    return {"value": value, "unit": unit, "confidence": 1.0, "status": "confirmed", "evidence": [EVIDENCE]}


def state(*, approved=True, status="confirmed"):
    payload = {
        "project_id": "p-1", "revision": 2,
        "units": {"length": traced("mm", status), "angle": traced("deg", status), "temperature": traced("C", status), "power": traced("W", status)},
        "coordinate_system": {"handedness": traced("right", status), "up_axis": traced("z", status), "origin_mm": traced((0.0, 0.0, 0.0), status)},
        "joints": [{"id": "j-1", "axis": traced((0.0, 0.0, 1.0), status), "rotation_range_deg": traced((-90.0, 90.0), status), "outer_radius_mm": traced(80.0, status), "inner_radius_mm": traced(60.0, status), "axial_length_mm": traced(110.0, status), "shell_wall_thickness_mm": traced(3.0, status)}],
        "components": [],
        "materials": [{"id": "al", "name": traced("Aluminum", status), "properties": {
            "density_kg_m3": property_value(2700.0, "kg/m3"),
            "thermal_conductivity_w_mk": property_value(167.0, "W/mK"),
            "specific_heat_j_kgk": property_value(896.0, "J/kgK"),
            "coefficient_thermal_expansion_1_k": property_value(2.3e-5, "1/K"),
            "youngs_modulus_pa": property_value(69e9, "Pa"),
            "poissons_ratio": property_value(0.33, None),
            "yield_strength_pa": property_value(276e6, "Pa"),
            "ultimate_tensile_strength_pa": property_value(310e6, "Pa"),
        }}],
        "interfaces": [],
        "thermal_loads": [{"id": "load-1", "component_id": traced("heater", status), "heat_w": traced(100.0, status)}],
        "operating_cases": [{"id": "case-1", "name": traced("nominal", status), "ambient_temperature_c": traced(25.0, status), "duty_cycle": traced(1.0, status), "thermal_load_ids": traced(["load-1"], status)}],
        "approvals": [], "unresolved": [],
    }
    if approved:
        payload["approvals"] = [{"id": "a-1", "subject": "engineering_state", "decision": "approved", "reviewed_by": "engineer", "revision": 1, "evidence": [EVIDENCE]}]
    return EngineeringState.model_validate(payload)


def artifact(fidelity="manufacturing_cad"):
    return Artifact.model_validate({"id": "cad-1", "role": "simulation_geometry", "uri": "file:///joint.step", "provider": "spaceclaim", "fidelity": fidelity, "content_hash": "a" * 64, "producer": "cad-agent", "version": "1", "input_revision": 2, "metadata": {"script_uri": "file:///joint.py"}})


def compile_handoff(engineering_state=None, geometry=None, api_version="V251"):
    return SimulationContractCompiler().compile(
        engineering_state or state(), geometry_artifact=geometry or artifact(), created_by="simulation-agent", model="CFD",
        joint_extensions={"j-1": {"segment_angle_deg": 120.0, "fins": {"count": 12, "height_mm": 8.0, "thickness_mm": 1.0, "pitch_deg": 30.0}}},
        named_selections=[{"name": "heater", "purpose": "load", "entity_type": "face"}], contacts=[],
        mesh_plan={"physics": "CFD", "element_order": "linear", "global_size_mm": 1.0, "boundary_layers": 5, "convergence_study_required": True},
        solver_plan={"solver": "Fluent", "analysis_type": "CFD", "max_iterations": 500, "residual_target": 1e-5},
        acceptance={"max_temperature_c": 90.0, "max_pressure_drop_pa": 5000.0, "require_converged": True}, api_version=api_version,
    )


def test_spaceclaim_v252_is_rejected():
    with pytest.raises(ValidationError):
        GeometryGenerator.model_validate({"provider": "spaceclaim", "api_version": "V252", "script_uri": "file:///x.py", "output_geometry_uri": "file:///x.step", "artifact_id": "a", "fidelity": "manufacturing_cad"})
    with pytest.raises(SimulationContractError, match="api_version"):
        compile_handoff(api_version="V252")


def test_unapproved_or_unconfirmed_state_cannot_compile():
    with pytest.raises(SimulationContractError, match="未授权"):
        compile_handoff(state(approved=False))
    with pytest.raises(SimulationContractError, match="未确认"):
        compile_handoff(state(status="extracted"))


def test_concept_mesh_cannot_be_simulation_geometry():
    with pytest.raises(SimulationContractError, match="concept_mesh"):
        compile_handoff(geometry=artifact("concept_mesh"))


def test_compile_and_ingest_valid_cfd_result():
    handoff = compile_handoff()
    assert handoff.geometry_generator.api_version == "V251"
    result = SimulationResultIngestor().ingest({
        "schema": "thermalforge.simulation_result", "version": "1.0.0", "project_id": "p-1", "engineering_revision": 2,
        "handoff_id": "handoff-1", "created_at": "2026-07-11T00:00:00Z", "model": "CFD", "solver": "Fluent",
        "cases": [{"case_id": "case-1", "converged": True, "max_temperature_c": 80.0, "pressure_drop_pa": 3000.0, "max_von_mises_stress_pa": None, "min_safety_factor": None}],
        "artifacts": [], "warnings": [],
    }, handoff)
    assert result.cases[0].converged


def test_lumped_result_rejects_field_outputs():
    handoff = compile_handoff().model_copy(update={"model": "lumped"})
    with pytest.raises(SimulationContractError, match="lumped"):
        SimulationResultIngestor().ingest({
            "schema": "thermalforge.simulation_result", "version": "1.0.0", "project_id": "p-1", "engineering_revision": 2,
            "handoff_id": "handoff-1", "created_at": "2026-07-11T00:00:00Z", "model": "lumped", "solver": "estimator",
            "cases": [{"case_id": "case-1", "converged": True, "max_temperature_c": 80.0, "pressure_drop_pa": 1.0, "max_von_mises_stress_pa": None, "min_safety_factor": None}],
            "artifacts": [], "warnings": [],
        }, handoff)
