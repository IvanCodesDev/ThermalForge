"""特性一：零依赖 STEP 解析 + 圆柱同轴分桶聚类单元测试（F1-P0-1 / OQ6）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.engine.step_reader import StepReader
from core.models.engineering_state import EngineeringState
from core.services.engineering_state_from_step import StepToEngineeringStateBuilder

STEP_PATH = Path(r"C:/Users/llwxy/Downloads/机械臂/IKI1602.STEP")


def _skip_if_missing(path: Path):
    if not path.exists():
        pytest.skip(f"真实 STEP 不存在：{path}")


def test_parse_real_step():
    _skip_if_missing(STEP_PATH)
    result = StepReader().parse(STEP_PATH)
    assert result.source_id == "step:IKI1602.STEP"
    assert len(result.cylinders) > 0
    assert result.part_count >= 1
    assert all(c.radius_mm > 0 for c in result.cylinders)
    resolved = [c for c in result.cylinders if c.axis_resolved]
    assert all(abs(c.axis[0]) + abs(c.axis[1]) + abs(c.axis[2]) > 0 for c in resolved)
    assert all(v >= 0 for v in result.bbox_mm)


def test_build_state_from_real_step():
    _skip_if_missing(STEP_PATH)
    result = StepReader().parse(STEP_PATH)
    state = StepToEngineeringStateBuilder().build("iki1602", result, STEP_PATH)
    assert isinstance(state, EngineeringState)
    assert state.revision == 1
    assert len(state.joints) >= 1
    assert len(state.materials) == 2
    assert len(state.thermal_loads) == len(state.joints)
    assert any(u.id == "unresolved-motor-params" for u in state.unresolved)
    # 关节几何自洽（满足 Joint 模型校验）
    for joint in state.joints:
        assert joint.inner_radius_mm.value < joint.outer_radius_mm.value
        assert joint.shell_wall_thickness_mm.value > 0


def test_no_cylinder_fallback(tmp_path):
    step = tmp_path / "no_cyl.step"
    # 无圆柱面 -> 应生成 1 个 needs_review 占位关节，且 EngineeringState 合法
    step.write_text(
        "ISO-10303-21;\nHEADER;\nFILE_NAME('x','');\nENDSEC;\n"
        "DATA;\n"
        "#1 = CARTESIAN_POINT ( 'NONE', ( 0.0, 0.0, 0.0 ) ) ;\n"
        "#2 = DIRECTION ( 'NONE', ( 0.0, 0.0, 1.0 ) ) ;\n"
        "ENDSEC;\nEND-ISO-10303-21;\n"
    )
    result = StepReader().parse(step)
    assert len(result.cylinders) == 0
    state = StepToEngineeringStateBuilder().build("p", result, step)
    assert len(state.joints) == 1
    assert state.joints[0].axis.status.value == "needs_review"
    assert any(u.id == "unresolved-no-cylinder" for u in state.unresolved)


def test_coaxial_cluster_two_cylinders(tmp_path):
    # 两个同轴、不同半径的圆柱 -> 1 个关节，inner < outer
    step = tmp_path / "coaxial.step"
    step.write_text(
        "ISO-10303-21;\nHEADER;\nFILE_NAME('c','');\nENDSEC;\n"
        "DATA;\n"
        "#1 = CARTESIAN_POINT ( 'NONE', ( 0.0, 0.0, 0.0 ) ) ;\n"
        "#2 = DIRECTION ( 'NONE', ( 0.0, 0.0, 1.0 ) ) ;\n"
        "#3 = DIRECTION ( 'NONE', ( 1.0, 0.0, 0.0 ) ) ;\n"
        "#4 = AXIS2_PLACEMENT_3D ( 'NONE', #1, #2, #3 ) ;\n"
        "#5 = CYLINDRICAL_SURFACE ( 'NONE', #4, 5.0 ) ;\n"
        "#6 = CARTESIAN_POINT ( 'NONE', ( 0.0, 0.0, 10.0 ) ) ;\n"
        "#7 = AXIS2_PLACEMENT_3D ( 'NONE', #6, #2, #3 ) ;\n"
        "#8 = CYLINDRICAL_SURFACE ( 'NONE', #7, 8.0 ) ;\n"
        "ENDSEC;\nEND-ISO-10303-21;\n"
    )
    result = StepReader().parse(step)
    assert len(result.cylinders) == 2
    state = StepToEngineeringStateBuilder().build("p", result, step)
    assert len(state.joints) >= 1
    for joint in state.joints:
        assert joint.inner_radius_mm.value < joint.outer_radius_mm.value
        assert joint.axis.value != (0.0, 0.0, 0.0)
