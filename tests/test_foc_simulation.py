from __future__ import annotations

import pytest

from core.engine.foc_simulation import FocJointInput, simulate_foc_joint


def test_foc_joint_simulation_allocates_the_declared_120w_loss_budget() -> None:
    result = simulate_foc_joint(FocJointInput())

    assert result.system.axes == 6
    assert result.system.focus_joint == "J4 肘关节"
    assert result.control.dc_bus_voltage_v == 48
    assert result.control.modulation == "SVPWM"
    assert result.control.current_loop_hz == 20_000
    assert result.total_continuous_loss_w == pytest.approx(120.0)
    assert result.total_peak_loss_w == pytest.approx(220.0)
    assert sum(source.continuous_w for source in result.loss_sources) == pytest.approx(120.0)
    assert sum(source.peak_w for source in result.loss_sources) == pytest.approx(220.0)


def test_foc_joint_simulation_exposes_motor_inverter_and_drivetrain_heat_paths() -> None:
    result = simulate_foc_joint(FocJointInput())
    grouped = result.grouped_continuous_losses_w

    assert grouped == {"pmsm": 60.0, "foc_inverter": 36.0, "drivetrain_and_control": 24.0}
    assert {source.id for source in result.loss_sources} == {
        "copper",
        "iron",
        "mosfet_conduction",
        "mosfet_switching",
        "reducer_bearing",
        "control_encoder",
    }
    assert all(source.heat_path for source in result.loss_sources)
    assert result.thermal_targets.mosfet_case_max_c == 85
    assert result.thermal_targets.winding_max_c == 100


def test_foc_joint_simulation_marks_budget_allocation_as_an_assumption_not_first_principles() -> None:
    result = simulate_foc_joint(FocJointInput())

    assert result.loss_model == "allocated_engineering_budget"
    assert result.is_first_principles is False
    assert any("实测" in item or "标定" in item for item in result.assumptions)
    assert "CFD" in " ".join(result.validation_tasks)


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param({"axes": 0}, id="zero-axes"),
        pytest.param({"axes": -1}, id="negative-axes"),
        pytest.param({"axes": float("nan")}, id="nan-axes"),
        pytest.param({"axes": float("inf")}, id="infinite-axes"),
        pytest.param({"axes": 6.5}, id="fractional-axes"),
        pytest.param({"axes": True}, id="boolean-axes"),
        pytest.param({"dc_bus_voltage_v": 0}, id="zero-dc-voltage"),
        pytest.param({"dc_bus_voltage_v": -1}, id="negative-dc-voltage"),
        pytest.param({"dc_bus_voltage_v": float("nan")}, id="nan-dc-voltage"),
        pytest.param({"dc_bus_voltage_v": float("inf")}, id="infinite-dc-voltage"),
        pytest.param(
            {"dc_bus_voltage_v": float("-inf")},
            id="negative-infinite-dc-voltage",
        ),
        pytest.param({"current_loop_hz": 0}, id="zero-current-loop"),
        pytest.param({"current_loop_hz": -1}, id="negative-current-loop"),
        pytest.param({"current_loop_hz": float("nan")}, id="nan-current-loop"),
        pytest.param({"current_loop_hz": float("inf")}, id="infinite-current-loop"),
        pytest.param({"current_loop_hz": 20_000.5}, id="fractional-current-loop"),
        pytest.param({"current_loop_hz": True}, id="boolean-current-loop"),
        pytest.param(
            {"continuous_loss_budget_w": -1},
            id="negative-continuous-budget",
        ),
        pytest.param(
            {"continuous_loss_budget_w": float("nan")},
            id="nan-continuous-budget",
        ),
        pytest.param(
            {"continuous_loss_budget_w": float("inf")},
            id="infinite-continuous-budget",
        ),
        pytest.param(
            {"continuous_loss_budget_w": float("-inf")},
            id="negative-infinite-continuous-budget",
        ),
        pytest.param({"peak_loss_budget_w": -1}, id="negative-peak-budget"),
        pytest.param({"peak_loss_budget_w": float("nan")}, id="nan-peak-budget"),
        pytest.param({"peak_loss_budget_w": float("inf")}, id="infinite-peak-budget"),
        pytest.param(
            {"peak_loss_budget_w": float("-inf")},
            id="negative-infinite-peak-budget",
        ),
        pytest.param(
            {"continuous_loss_budget_w": 121, "peak_loss_budget_w": 120},
            id="peak-below-continuous",
        ),
    ],
)
def test_foc_joint_input_rejects_invalid_operating_values(
    overrides: dict[str, float],
) -> None:
    with pytest.raises(ValueError):
        FocJointInput(**overrides)


def test_foc_joint_simulation_propagates_a_custom_valid_input() -> None:
    result = simulate_foc_joint(
        FocJointInput(
            axes=7,
            focus_joint="J5 腕关节",
            motor_type="IPMSM",
            dc_bus_voltage_v=72,
            modulation="DPWM",
            current_loop_hz=25_000,
            continuous_loss_budget_w=90,
            peak_loss_budget_w=180,
        )
    )

    assert (result.system.axes, result.system.focus_joint, result.system.motor_type) == (
        7,
        "J5 腕关节",
        "IPMSM",
    )
    assert (
        result.control.dc_bus_voltage_v,
        result.control.modulation,
        result.control.current_loop_hz,
    ) == (72, "DPWM", 25_000)
    assert result.total_continuous_loss_w == pytest.approx(90)
    assert result.total_peak_loss_w == pytest.approx(180)
