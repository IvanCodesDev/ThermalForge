"""Use the governed backend LLM to generate GPT Image 2 prompts from real FOC demo data."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys
from typing import Any, Literal


ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.agents.contracts import ExecutionContext
from core.agents.definitions import build_agent_registry
from core.agents.execution import AgentExecutionService, build_default_quality_gates, build_default_tool_adapters
from core.config import Settings
from core.models.foc_image_prompt import FocArmMultiviewPromptOutput, FocArmMultiviewPromptRequest
from core.providers.openai_models import OpenAIModelsClient
from core.services.foc_demo import FocDemoRepository, redact_backend_output

OUTPUT = ROOT / "outputs" / "foc_arm_multiview_prompts_agent_output.json"

SYSTEM_INSTRUCTIONS = """
You are ThermalForge's governed industrial-design prompt compiler. Use only the supplied real FOC demo snapshot as engineering evidence. Produce prompts for GPT Image 2 that create a visually exceptional four-degree-of-freedom BLDC/FOC robotic-arm concept suitable for consistent multi-view reconstruction in Hyper3D Rodin Gen-2.

The source snapshot describes a validated demo scenario for a high-heat robot elbow joint. Preserve its actual thermal facts and component architecture: 48 V PMSM/BLDC-class actuator, FOC inverter, encoder, 80:1 harmonic reducer, 120 W continuous thermal dissipation, 220 W short peak thermal dissipation, 35 C ambient, winding target below 100 C, MOSFET case target below 85 C, 6061-T6 CNC housing, integrated external heat-spreading ribs, inverter cold plate/baseplate, stator-to-housing thermal ring, no dedicated fan, optional annular liquid-cooling path, identifiable housing, cold plate, thermal ring, reducer interface, sealed cover and cable interface.

The requested full arm has exactly four actuated joints: J1 base yaw, J2 shoulder pitch, J3 elbow pitch and J4 coaxial wrist roll. Treat the full-arm kinematic arrangement and any unprovided whole-arm dimensions as explicit concept assumptions, never as source facts. Do not claim CAD, CFD, FEA, manufacturing or performance validation. The existing thermal result is screening only and not CFD.

Return one strict JSON object matching the requested schema. Do not wrap it in markdown. Prompts must be in English because they will be sent unchanged to GPT Image 2. Each view must describe the exact same robot, same neutral pose, same proportions, same part boundaries, same cooling features, same materials and colors. Require a clean light-gray studio background, orthographic or minimal-perspective technical product rendering, full object visible, no crop, no text, no logo and no scenery.

The mother three-quarter prompt establishes the authoritative design. The front, left, rear and top prompts must instruct GPT Image 2 to use the mother image as the only authoritative image reference and preserve the design exactly. Also generate an elbow_section prompt for a clean longitudinal engineering cutaway through the J3 elbow actuator axis. The cutaway must expose the PMSM/BLDC-class motor, 80:1 harmonic reducer interface, encoder, FOC inverter cold plate, thermal pad, stator-to-housing thermal ring, 6061-T6 load-bearing housing, external heat-spreading ribs, sealed cover, protected cable interface and optional annular liquid-cooling path. It must preserve the same external design and clearly distinguish known FOC source facts from conceptual packaging assumptions. Include a negative prompt, a Hyper3D input recommendation and an explicit source-facts-versus-assumptions ledger.

The aesthetic direction must visibly communicate ThermalForge's core product: AI thermal-design copilot, parameter-aware cooling architecture and engineering traceability. Use premium aerospace robotics, graphite load-bearing exoskeleton, machined aluminum actuator housings, restrained cyan for control/coolant paths and restrained amber for thermal zones. Thermal structures must be functional and integrated, not decorative neon or fantasy styling.
""".strip()



def _build_provider(client: OpenAIModelsClient):
    async def provider(model: str, prompt: str, governed_payload: dict[str, Any]) -> dict[str, Any]:
        response = await client.create_response(
            model=model,
            instructions=f"{prompt}\n\n{SYSTEM_INSTRUCTIONS}",
            input_data=json.dumps(governed_payload, ensure_ascii=False),
            max_output_tokens=6000,
            metadata={
                "workflow": "foc_arm_multiview_prompt_generation",
                "agent_id": "foc_arm_multiview_prompt_agent",
            },
        )
        return OpenAIModelsClient.extract_json_object(response)

    return provider


async def main() -> None:
    settings = Settings()
    repository = FocDemoRepository()
    snapshot = repository.snapshot()
    snapshot_payload = snapshot.model_dump(mode="json")
    snapshot_json = json.dumps(snapshot_payload, ensure_ascii=False, sort_keys=True)

    request = FocArmMultiviewPromptRequest(
        target_product="ThermalForge flagship four-DOF BLDC/FOC robotic arm",
        dof=4,
        image_model="gpt-image-2",
        reconstruction_target="Hyper3D Rodin Gen-2",
        required_views=["mother_three_quarter", "front", "left", "rear", "top", "elbow_section"],
        visual_priority="Premium industrial aesthetics with visibly functional thermal architecture and multi-view consistency",
        source_snapshot=snapshot_payload,
    )

    registry = build_agent_registry(settings)
    client = OpenAIModelsClient(settings)
    execution = AgentExecutionService(
        registry,
        _build_provider(client),
        tools=build_default_tool_adapters(),
        quality_gates=build_default_quality_gates(),
    )

    output = await execution.execute(
        "foc_arm_multiview_prompt_agent",
        request,
        ExecutionContext(
            project_id="thermalforge-foc-arm-demo",
            input_artifact_ids=("outputs/foc_robot_arm_backend_output.json",),
        ),
    )
    validated = FocArmMultiviewPromptOutput.model_validate(output)
    records = execution.list(project_id="thermalforge-foc-arm-demo")
    record = records[-1]

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": {
            "repository": "core.services.foc_demo.FocDemoRepository",
            "artifact": "outputs/foc_robot_arm_backend_output.json",
            "snapshot_sha256": sha256(snapshot_json.encode("utf-8")).hexdigest(),
            "scenario": snapshot.scenario,
            "thermal_fidelity": snapshot.thermal.fidelity,
            "not_cfd": snapshot.thermal.not_cfd,
        },
        "agent_execution": {
            "execution_id": str(record.id),
            "agent_id": record.agent_id,
            "agent_version": record.agent_version,
            "prompt_id": record.prompt_id,
            "prompt_version": record.prompt_version,
            "prompt_hash": record.prompt_hash,
            "model": record.model,
            "status": record.status,
            "attempts": record.metadata.get("attempts"),
        },
        "request": request.model_dump(mode="json"),
        "agent_output": validated.model_dump(mode="json"),
    }
    safe_report = redact_backend_output(report)
    OUTPUT.write_text(json.dumps(safe_report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "execution_id": str(record.id), "status": record.status}, ensure_ascii=False))


if __name__ == "__main__":
    asyncio.run(main())
