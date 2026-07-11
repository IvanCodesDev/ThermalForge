"""Mechanical 隔离 Adapter 边界（默认禁用真实执行）。"""
from core.adapters.base import AdapterExecutionResult
from core.models.simulation_contract import SimulationHandoffContract

class MechanicalAdapter:
    def execute(self, handoff: SimulationHandoffContract) -> AdapterExecutionResult:
        if handoff.model not in {"FEA", "coupled_CFD_FEA"}:
            raise ValueError("Mechanical 仅接受 FEA handoff")
        return AdapterExecutionResult(status="disabled", error="真实 Mechanical 执行未授权")
