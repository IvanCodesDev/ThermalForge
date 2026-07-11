"""特性一：SpaceClaim Handoff 编译器单元测试（OQ3 / OQ4 / OQ5）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.adapters.spaceclaim_v251 import SpaceClaimV251Renderer
from core.engine.step_reader import StepReader
from core.models.agent_pipeline import EvidenceRef
from core.models.engineering_state import (
    CoordinateSystem,
    EngineeringState,
    Joint,
    Material,
    TracedValue,
    Units,
    ValueStatus,
)
from core.models.spaceclaim_contract import SpaceClaimHandoffContract
from core.services.engineering_state_from_step import StepToEngineeringStateBuilder
from core.services.spaceclaim_handoff import SpaceClaimHandoffCompiler

STEP_PATH = Path(r"C:/Users/llwxy/Downloads/机械臂/IKI1602.STEP")


def _traced(value, status="assumed", source="default:geometry", loc="x"):
    return TracedValue(
        value=value,
        status=ValueStatus(status),
        evidence=[EvidenceRef(source_id=source, locator=loc)],
    )


def _skip_if_missing(path: Path):
    if not path.exists():
        pytest.skip(f"真实 STEP 不存在：{path}")


def _state_from_real_step():
    _skip_if_missing(STEP_PATH)
    result = StepReader().parse(STEP_PATH)
    return StepToEngineeringStateBuilder().build("iki1602", result, STEP_PATH)


def test_compile_real_state():
    state = _state_from_real_step()
    contract = SpaceClaimHandoffCompiler().compile(state)
    assert isinstance(contract, SpaceClaimHandoffContract)
    # OQ4：几何交接直接 approved，不走仿真审批门
    assert contract.approval_status == "approved"
    assert contract.id == "spaceclaim-handoff"
    assert len(contract.joints) == len(state.joints)
    assert len(contract.materials) == len(state.materials)
    # OQ3：分瓣角默认 360，翅片默认
    jp = contract.joints[0]
    assert jp.segment_angle_deg == 360.0
    assert jp.fins.count == 12
    assert jp.fins.height_mm == 8.0
    assert jp.fins.thickness_mm == 1.0
    assert jp.fins.pitch_deg == 30.0
    # named selections 唯一且引用自洽（模型校验通过）
    names = [n.name for n in contract.named_selections]
    assert len(names) == len(set(names))
    # 8 字段材质
    for material in contract.materials:
        assert material.density_kg_m3 > 0
        assert material.youngs_modulus_pa > 0


def test_handoff_json_roundtrip():
    state = _state_from_real_step()
    contract = SpaceClaimHandoffCompiler().compile(state)
    dumped = contract.model_dump_json()
    revalidated = SpaceClaimHandoffContract.model_validate_json(dumped)
    assert revalidated.approval_status == "approved"
    assert len(revalidated.joints) == len(contract.joints)


def test_oq5_missing_material_fields_filled():
    # 构造一个材质属性（8 字段）缺失的 EngineeringState -> 编译器补缺自默认材质表
    joint = Joint(
        id="joint-1",
        axis=_traced((0.0, 0.0, 1.0)),
        rotation_range_deg=_traced((-180.0, 180.0)),
        outer_radius_mm=_traced(30.0),
        inner_radius_mm=_traced(20.0),
        axial_length_mm=_traced(50.0),
        shell_wall_thickness_mm=_traced(3.0),
    )
    material = Material(id="al", name=_traced("Aluminum"), properties={})
    units = Units(
        length=_traced("mm"), angle=_traced("deg"), temperature=_traced("C"), power=_traced("W")
    )
    coord = CoordinateSystem(
        handedness=_traced("right"), up_axis=_traced("z"), origin_mm=_traced((0.0, 0.0, 0.0))
    )
    state = EngineeringState(
        project_id="p",
        revision=1,
        units=units,
        coordinate_system=coord,
        joints=[joint],
        materials=[material],
    )
    contract = SpaceClaimHandoffCompiler().compile(state)
    al = next(m for m in contract.materials if m.material_id == "al")
    # OQ5：补缺自默认材质表（与 spaceclaim-handoff.v1.json 对齐）
    assert al.density_kg_m3 == 2700.0
    assert al.thermal_conductivity_w_mk == 167.0
    assert al.youngs_modulus_pa == 69e9
    assert al.yield_strength_pa == 276e6


def test_renderer_writes_py(tmp_path):
    joint = Joint(
        id="joint-1",
        axis=_traced((0.0, 0.0, 1.0)),
        rotation_range_deg=_traced((-180.0, 180.0)),
        outer_radius_mm=_traced(30.0),
        inner_radius_mm=_traced(20.0),
        axial_length_mm=_traced(50.0),
        shell_wall_thickness_mm=_traced(3.0),
    )
    material = Material(id="al", name=_traced("Aluminum"), properties={})
    units = Units(
        length=_traced("mm"), angle=_traced("deg"), temperature=_traced("C"), power=_traced("W")
    )
    coord = CoordinateSystem(
        handedness=_traced("right"), up_axis=_traced("z"), origin_mm=_traced((0.0, 0.0, 0.0))
    )
    state = EngineeringState(
        project_id="p",
        revision=1,
        units=units,
        coordinate_system=coord,
        joints=[joint],
        materials=[material],
    )
    contract = SpaceClaimHandoffCompiler().compile(state)
    path = SpaceClaimV251Renderer().write(contract, tmp_path)
    assert path.exists()
    assert path.name == "spaceclaim-handoff.py"
    assert "HANDOFF" in path.read_text(encoding="utf-8")
