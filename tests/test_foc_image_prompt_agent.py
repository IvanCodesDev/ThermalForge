from core.agents.contracts import ExecutionContext
from core.agents.definitions import build_agent_registry
from core.agents.execution import AgentExecutionService, build_default_quality_gates, build_default_tool_adapters
from core.config import Settings
from core.models.foc_image_prompt import FocArmMultiviewPromptOutput, FocArmMultiviewPromptRequest


def _request() -> FocArmMultiviewPromptRequest:
    return FocArmMultiviewPromptRequest(
        target_product="ThermalForge four-DOF arm",
        dof=4,
        image_model="gpt-image-2",
        reconstruction_target="Hyper3D Rodin Gen-2",
        required_views=["mother_three_quarter", "front", "left", "rear", "top", "elbow_section"],
        visual_priority="thermal engineering",
        source_snapshot={"engineering_input": "120 W continuous, 220 W peak", "thermal": {"not_cfd": True}},
    )


def _output() -> dict:
    common = "Same exact four-degree-of-freedom robotic arm with graphite structure, aluminum joints, integrated cooling fins and thermal rings. "
    return {
        "design_name": "ThermalForge FOC-4",
        "source_facts": [f"fact {index}" for index in range(8)],
        "concept_assumptions": ["four-axis whole-arm layout", "neutral pose", "whole-arm proportions"],
        "shared_identity": common * 3,
        "views": [
            {"id": view_id, "camera": "Exact orthographic technical camera centered on robot", "purpose": "Consistent reference for multi-view reconstruction", "prompt": common * 4}
            for view_id in ["mother_three_quarter", "front", "left", "rear", "top", "elbow_section"]
        ],
        "negative_prompt": "No fantasy, no extra joints, no six-axis layout, no humanoid hand, no text, no logo, no scenery, no floating parts, no fused organic shell. " * 2,
        "image_settings": {"model": "gpt-image-2", "size": "1024x1024", "quality": "high", "output_format": "png", "background": "opaque"},
        "hyper3d_guidance": ["Use mother image first", "Preserve pose", "Preserve part seams", "Reject inconsistent views"],
        "fidelity_notice": "This is a concept-image prompt derived from screening data and is not CAD, CFD, FEA, manufacturing, or performance validation.",
    }


def test_multiview_agent_is_registered() -> None:
    registry = build_agent_registry(Settings())
    definition = registry.get("foc_arm_multiview_prompt_agent")
    assert definition.prompt_id == "foc_arm_multiview_prompt.v1"
    assert definition.tools == ("foc_demo_snapshot_reader",)
    assert definition.model == "gpt-5.6-sol"


def test_multiview_agent_executes_with_snapshot_tool() -> None:
    seen = {}

    async def provider(model, prompt, governed_payload):
        seen.update(governed_payload)
        return _output()

    service = AgentExecutionService(
        build_agent_registry(Settings(thermalforge_mode="development")),
        provider,
        tools=build_default_tool_adapters(),
        quality_gates=build_default_quality_gates(),
    )

    import asyncio
    result = asyncio.run(service.execute(
        "foc_arm_multiview_prompt_agent",
        _request(),
        ExecutionContext(project_id="test-foc-arm"),
    ))

    validated = FocArmMultiviewPromptOutput.model_validate(result)
    assert {view.id for view in validated.views} == {"mother_three_quarter", "front", "left", "rear", "top", "elbow_section"}
    assert seen["tool_outputs"]["foc_demo_snapshot_reader"]["thermal"]["not_cfd"] is True
