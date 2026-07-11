"""特性二：文档模板单元测试（OQ2）。"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from core.knowledge.templates import (
    MaterialSpecTemplate,
    MotorDatasheetTemplate,
    RobotArmSpecTemplate,
)


def test_motor_default_bldc():
    assert MotorDatasheetTemplate().motor_type == "BLDC"


def test_motor_with_values():
    motor = MotorDatasheetTemplate(rated_power_w=50.0, efficiency=0.85)
    assert motor.rated_power_w == 50.0
    assert motor.efficiency == 0.85
    assert motor.motor_type == "BLDC"


def test_robot_arm_default_bldc():
    assert RobotArmSpecTemplate().motor_type == "BLDC"
    arm = RobotArmSpecTemplate(dof=6, reach_mm=500.0, payload_kg=3.0)
    assert arm.dof == 6
    assert arm.reach_mm == 500.0


def test_material_requires_name():
    with pytest.raises(ValidationError):
        MaterialSpecTemplate()
    material = MaterialSpecTemplate(name="Al", density_kg_m3=2700.0)
    assert material.name == "Al"
    assert material.density_kg_m3 == 2700.0


def test_extra_fields_forbidden():
    with pytest.raises(ValidationError):
        MotorDatasheetTemplate(unknown_field=1)
    with pytest.raises(ValidationError):
        RobotArmSpecTemplate(motor_type="BLDC", bogus=2)
