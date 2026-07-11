import json

import pytest

from app.engineering.schemas import EngineeringBrief
from app.llm.base import StructuredLLMRequest
from app.llm.fixture import FixtureLLMProvider


@pytest.mark.asyncio
async def test_fixture_provider_extracts_a_repeatable_local_brief() -> None:
    context = {
        "task_prompt": "保持原厂孔位，外壳可拆卸。",
        "clarifications": [],
        "document_bundle": {
            "chunks": [
                {
                    "id": "source-1:chunk:0",
                    "source_artifact_id": "source-1",
                    "page_number": 1,
                    "text": (
                        "电机持续功率 120 W，环境温度 25°C，"
                        "可用空间 180 mm × 90 mm × 70 mm。"
                    ),
                }
            ]
        },
    }

    result = await FixtureLLMProvider().generate_structured(
        StructuredLLMRequest(
            system_prompt="test",
            user_prompt=json.dumps(context, ensure_ascii=False),
            response_model=EngineeringBrief,
            prompt_version="test-v1",
        )
    )

    assert result.value.heat_sources[0].power_w == 120
    assert result.value.environment is not None
    assert result.value.environment.ambient_temp_c == 25
    assert result.value.envelope is not None
    assert result.value.envelope.width_mm == 180
    assert result.value.mounting_constraints == ["保持原厂孔位"]
