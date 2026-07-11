"""版本化 Agent 系统 JSON 示例契约测试。"""
from pathlib import Path

from core.agents.contracts import AgentDefinition
from core.models.engineering_state import EngineeringState
from core.models.simulation_contract import SimulationHandoffContract, SimulationResultContract
from core.models.spaceclaim_contract import SpaceClaimHandoffContract

EXAMPLES = Path(__file__).parents[1] / "docs" / "agent-system" / "examples"


def test_versioned_json_examples_validate_against_pydantic_contracts() -> None:
    contracts = {
        "agent-definition.v1.json": AgentDefinition,
        "engineering-state.v1.json": EngineeringState,
        "spaceclaim-handoff.v1.json": SpaceClaimHandoffContract,
        "simulation-handoff.v1.json": SimulationHandoffContract,
        "simulation-result.v1.json": SimulationResultContract,
    }
    assert {path.name for path in EXAMPLES.glob("*.json")} == set(contracts)
    for filename, contract in contracts.items():
        contract.model_validate_json((EXAMPLES / filename).read_text(encoding="utf-8"), strict=False)
