from __future__ import annotations

from hashlib import sha256

import pytest
from pydantic import ValidationError

from core.agents import AgentDefinition, PromptDefinition, PromptRegistry, build_agent_registry
from core.config import Settings


def test_builtin_agents_use_only_configured_text_model_and_explicit_policies():
    settings = Settings(OPENAI_TEXT_MODEL="gpt-5.6-sol")
    registry = build_agent_registry(settings)

    expected = {
        "specification_agent",
        "hyper3d_compiler_agent",
        "component_analysis_agent",
        "simulation_planner_agent",
        "result_interpreter_agent",
    }
    for agent_id in expected:
        definition = registry.get(agent_id)
        assert definition.model == settings.openai_text_model == "gpt-5.6-sol"
        policy = registry.policy_for(agent_id)
        assert policy.allowed_tools == definition.tools
        assert set(policy.denied_permissions) == {"network", "filesystem_write", "shell", "secrets_read"}


def test_registry_rejects_agent_model_other_than_settings_text_model():
    settings = Settings(OPENAI_TEXT_MODEL="gpt-5.6-sol")
    registry = build_agent_registry(settings)
    prompt = registry.prompts.get("specification_extraction.v1")
    with pytest.raises(ValueError, match="Settings.openai_text_model"):
        registry.register(AgentDefinition(
            id="invalid_agent",
            version="1.0.0",
            model="other-model",
            role="invalid",
            prompt_id=prompt.id,
            input_schema={},
            output_schema={},
        ))


def test_prompt_registry_verifies_template_sha256():
    template = "stable prompt"
    valid = PromptDefinition(
        id="stable.v1",
        version="1.0.0",
        template=template,
        sha256=sha256(template.encode("utf-8")).hexdigest(),
    )
    assert PromptRegistry((valid,)).get("stable.v1") == valid

    invalid = valid.model_copy(update={"id": "invalid.v1", "sha256": "0" * 64})
    with pytest.raises(ValueError, match="sha256"):
        PromptRegistry((invalid,))


def test_protocol_contracts_are_strict_and_forbid_extra_fields():
    with pytest.raises(ValidationError):
        PromptDefinition(
            id="prompt.v1",
            version="1.0.0",
            template="x",
            sha256=sha256(b"x").hexdigest(),
            unexpected=True,
        )
