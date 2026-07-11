from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from app.config import Settings
from app.domain.enums import ArtifactKind, QualityStatus, TaskStatus
from app.domain.errors import InvalidLLMOutput
from app.engineering.schemas import (
    EngineeringBrief,
    Envelope,
    EvidenceRef,
    HeatSource,
    MassBudget,
    OperatingEnvironment,
)
from app.llm.base import LLMResult
from app.main import create_app
from app.repositories.artifacts import ArtifactRepository
from app.services.tasks import TaskService
from app.services.thermal_analysis import ThermalAnalysisService
from app.thermal.schemas import (
    ComponentExplanation,
    DesignRisk,
    ThermalOptimizationDecision,
)


class StaticOptimizationProvider:
    def __init__(self, decision: ThermalOptimizationDecision) -> None:
        self.decision = decision
        self.last_system_prompt = ""
        self.last_user_prompt = ""

    async def generate_structured(
        self,
        request: Any,
    ) -> LLMResult[ThermalOptimizationDecision]:
        self.last_system_prompt = request.system_prompt
        self.last_user_prompt = request.user_prompt
        return LLMResult(
            value=self.decision,
            provider="fixture",
            model="thermal-optimization-fixture",
            request_id="fixture-thermal-request",
            input_tokens=220,
            output_tokens=140,
            latency_ms=15,
        )


def settings(tmp_path: Path) -> Settings:
    return Settings(
        environment="test",
        database_url=f"sqlite+aiosqlite:///{(tmp_path / 'thermal.db').as_posix()}",
        artifact_root=tmp_path / "artifacts",
        upload_temp_root=tmp_path / "uploads",
        queue_enabled=False,
        cors_origins=[],
    )


def complete_brief() -> EngineeringBrief:
    evidence = EvidenceRef(
        source_kind="user_prompt",
        quote="电机持续功率 120 W，环境温度 25°C，增重不得超过 8%。",
    )
    return EngineeringBrief(
        project_title="机器人膝关节热增强",
        heat_sources=[
            HeatSource(
                name="电机",
                power_w=120,
                maximum_temperature_c=80,
                duty_cycle_percent=85,
                evidence=[evidence],
                confidence=1,
            )
        ],
        environment=OperatingEnvironment(
            ambient_temp_c=25,
            airflow_m_s=0.3,
            evidence=[evidence],
            confidence=1,
        ),
        envelope=Envelope(
            width_mm=180,
            height_mm=90,
            depth_mm=70,
            evidence=[evidence],
            confidence=1,
        ),
        mass_budget=MassBudget(
            maximum_added_mass_g=150,
            maximum_added_mass_percent=8,
            evidence=[evidence],
            confidence=1,
        ),
        mounting_constraints=["不得超出运动包络", "保持原厂孔位"],
        required_features=["外壳可拆卸"],
        prohibited_changes=["不改电机", "不改减速器"],
        manufacturing_constraints=["允许 CNC 或金属增材制造"],
        overall_confidence=0.98,
    )


def valid_decision(solution_id: str = "vein-bridge") -> ThermalOptimizationDecision:
    return ThermalOptimizationDecision(
        selected_solution_id=solution_id,
        rationale="该方案在热扩散、可拆卸性和安装兼容性之间最均衡。",
        heat_transfer_path=["电机壳体", "可逆导热桥", "叶脉扩散外壳", "环境空气"],
        material_recommendations=["AL-6061-T6", "柔性石墨导热界面"],
        geometry_anchors=["原厂孔位", "外壳热点区域", "线束与轴承避让区"],
        manufacturing_recommendations=["外壳采用 CNC 加工", "导热桥独立可拆装"],
        component_explanations=[
            ComponentExplanation(
                component_id="thermal-bridge",
                name="可逆导热桥",
                explanation="把局部热流导向外置扩散结构，同时保留拆装能力。",
            ),
            ComponentExplanation(
                component_id="vein-shell",
                name="叶脉扩散外壳",
                explanation="沿分叉路径扩散热点并增大空气侧换热面积。",
            ),
        ],
        risks=[
            DesignRisk(
                source="engineering_brief",
                description="缺少真实材料接触热阻和样机温升数据。",
                impact="high",
                recommended_action="制造前补充接触热阻测试并进行样机复测。",
            )
        ],
        unverified_items=["导热界面压紧力", "动态运动包络实测"],
        requires_human_confirmation=True,
    )


async def prepare_thermal_task(
    client: AsyncClient,
    app: Any,
) -> tuple[str, str]:
    project = (await client.post("/v1/projects", json={"name": "热设计"})).json()
    task = (
        await client.post(
            f"/v1/projects/{project['id']}/tasks",
            headers={"Idempotency-Key": "thermal-design-task"},
            json={"prompt": "设计可拆卸机器人关节散热外壳"},
        )
    ).json()
    task_id = str(task["id"])
    brief = complete_brief()
    payload = brief.model_dump_json(indent=2).encode()
    stored = await app.state.artifact_store.put_bytes(
        task_id=task_id,
        relative_path="engineering-brief/test/engineering-brief.json",
        payload=payload,
        mime_type="application/json",
    )

    async with app.state.database.session() as session:
        artifact = await ArtifactRepository(session).create(
            task_id=task_id,
            kind=ArtifactKind.ENGINEERING_BRIEF,
            stored=stored,
            provider="fixture",
            provider_model="engineering-brief-fixture",
            prompt_version="engineering-brief-v1",
            quality_status=QualityStatus.APPROVED,
        )
        await session.commit()
        tasks = TaskService(session)
        for status in (
            TaskStatus.UPLOADED,
            TaskStatus.PARSING,
            TaskStatus.BRIEFING,
            TaskStatus.THERMAL_ANALYSIS,
        ):
            await tasks.transition(task_id, status)

    return task_id, artifact.id


@pytest.mark.asyncio
async def test_generates_authoritative_analysis_and_llm_optimized_design(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        task_id, brief_artifact_id = await prepare_thermal_task(client, app)
        provider = StaticOptimizationProvider(valid_decision())

        async with app.state.database.session() as session:
            design_artifact = await ThermalAnalysisService(
                session=session,
                artifact_store=app.state.artifact_store,
                llm_provider=provider,
                settings=app.state.settings,
            ).generate(task_id)

        task = await client.get(f"/v1/tasks/{task_id}")
        analysis_response = await client.get(
            f"/v1/tasks/{task_id}/thermal-analysis"
        )
        design_response = await client.get(f"/v1/tasks/{task_id}/thermal-design")
        artifacts = (await client.get(f"/v1/tasks/{task_id}/artifacts")).json()

    design = design_response.json()
    analysis = analysis_response.json()
    assert task.json()["status"] == "concept_imaging"
    assert analysis_response.status_code == 200
    assert design_response.status_code == 200
    assert design["engineering_brief_artifact_id"] == brief_artifact_id
    assert design["thermal_analysis_artifact_id"]
    assert design["selected_solution"]["solution_id"] == "vein-bridge"
    assert (
        design["selected_solution"]["max_temperature_c"]
        == next(
            candidate["maxTemperatureC"]
            for candidate in analysis["candidates"]
            if candidate["solutionId"] == "vein-bridge"
        )
    )
    assert design["requires_human_confirmation"] is True
    assert "gyroid" not in provider.last_user_prompt
    assert "vein-bridge" in provider.last_user_prompt
    assert "may not invent" in provider.last_system_prompt
    assert design_artifact.metadata_json["prompt_version"] == (
        "thermal-optimization-v1"
    )
    assert [artifact["kind"] for artifact in artifacts][-2:] == [
        "thermal_analysis",
        "thermal_design",
    ]


@pytest.mark.asyncio
async def test_rejects_llm_selection_outside_the_compliant_candidate_set(
    tmp_path: Path,
) -> None:
    app = create_app(settings(tmp_path))
    async with (
        app.router.lifespan_context(app),
        AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client,
    ):
        task_id, _ = await prepare_thermal_task(client, app)
        provider = StaticOptimizationProvider(valid_decision("invented-solution"))

        with pytest.raises(InvalidLLMOutput):
            async with app.state.database.session() as session:
                await ThermalAnalysisService(
                    session=session,
                    artifact_store=app.state.artifact_store,
                    llm_provider=provider,
                    settings=app.state.settings,
                ).generate(task_id)

        task = await client.get(f"/v1/tasks/{task_id}")
        retried = await client.post(f"/v1/tasks/{task_id}/retry")

    assert task.json()["status"] == "failed"
    assert retried.json()["status"] == "thermal_analysis"
