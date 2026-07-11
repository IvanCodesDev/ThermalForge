"""Fluent 隔离 Adapter 边界（默认禁用真实执行）。"""
from core.adapters.base import AdapterExecutionResult
from core.models.simulation_contract import SimulationHandoffContract

class FluentAdapter:
    def execute(self, handoff: SimulationHandoffContract) -> AdapterExecutionResult:
        if handoff.model not in {"CFD", "coupled_CFD_FEA"}:
            raise ValueError("Fluent 仅接受 CFD handoff")
        return AdapterExecutionResult(status="disabled", error="真实 Fluent 执行未授权")
