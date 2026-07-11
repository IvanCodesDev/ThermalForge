"""ThermalForge 正式 Agent 协议。"""
from core.agents.contracts import (
    AgentDefinition,
    ExecutionRecord,
    PromptDefinition,
    QualityGate,
    RetryPolicy,
    SkillDefinition,
    ToolDefinition,
    ToolPolicy,
)
from core.agents.definitions import build_agent_registry
from core.agents.registry import AgentRegistry, PromptRegistry, SkillRegistry

__all__ = [
    "AgentDefinition",
    "AgentRegistry",
    "ExecutionRecord",
    "PromptDefinition",
    "PromptRegistry",
    "QualityGate",
    "RetryPolicy",
    "SkillDefinition",
    "SkillRegistry",
    "ToolDefinition",
    "ToolPolicy",
    "build_agent_registry",
]
