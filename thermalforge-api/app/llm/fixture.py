import json
import re
from dataclasses import dataclass
from time import perf_counter
from typing import cast

from app.domain.errors import InvalidLLMOutput
from app.engineering.schemas import (
    EngineeringBrief,
    Envelope,
    EvidenceRef,
    HeatSource,
    OperatingEnvironment,
)
from app.llm.base import (
    LLMResult,
    StructuredLLMRequest,
    StructuredOutput,
)
from app.thermal.schemas import (
    ComponentExplanation,
    DesignRisk,
    ThermalOptimizationDecision,
)

_POWER_PATTERN = re.compile(r"(?<!\d)(\d+(?:\.\d+)?)\s*[Ww](?!\w)")
_AMBIENT_PATTERN = re.compile(
    r"(?:环境温度|ambient\s+temperature)[^\d-]{0,12}(-?\d+(?:\.\d+)?)\s*°?\s*[Cc]",
    re.IGNORECASE,
)
_ENVELOPE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*mm\s*[×xX*]\s*"
    r"(\d+(?:\.\d+)?)\s*mm\s*[×xX*]\s*"
    r"(\d+(?:\.\d+)?)\s*mm",
    re.IGNORECASE,
)


@dataclass(frozen=True, slots=True)
class _SourceText:
    text: str
    evidence: EvidenceRef


class FixtureLLMProvider:
    """Deterministic local substitute; never presented as a real model result."""

    @staticmethod
    def _source_texts(context: dict[str, object]) -> list[_SourceText]:
        sources: list[_SourceText] = []
        task_prompt = str(context.get("task_prompt") or "")
        if task_prompt:
            sources.append(
                _SourceText(
                    text=task_prompt,
                    evidence=EvidenceRef(
                        source_kind="user_prompt",
                        quote=task_prompt[:500],
                    ),
                )
            )

        for clarification in cast(
            list[dict[str, object]],
            context.get("clarifications") or [],
        ):
            answer = str(clarification.get("answer") or "")
            clarification_id = str(clarification.get("id") or "")
            if answer and clarification_id:
                sources.append(
                    _SourceText(
                        text=answer,
                        evidence=EvidenceRef(
                            source_kind="clarification",
                            quote=answer[:500],
                            clarification_id=clarification_id,
                        ),
                    )
                )

        bundle = cast(dict[str, object], context.get("document_bundle") or {})
        for chunk in cast(
            list[dict[str, object]],
            bundle.get("chunks") or [],
        ):
            text = str(chunk.get("text") or "")
            chunk_id = str(chunk.get("id") or "")
            artifact_id = str(chunk.get("source_artifact_id") or "")
            if text and chunk_id and artifact_id:
                page_number = chunk.get("page_number")
                normalized_page_number = (
                    int(page_number)
                    if isinstance(page_number, (int, str))
                    else None
                )
                sources.append(
                    _SourceText(
                        text=text,
                        evidence=EvidenceRef(
                            source_kind="document",
                            quote=text[:500],
                            artifact_id=artifact_id,
                            chunk_id=chunk_id,
                            page_number=normalized_page_number,
                        ),
                    )
                )
        return sources

    @staticmethod
    def _find(
        sources: list[_SourceText],
        pattern: re.Pattern[str],
    ) -> tuple[re.Match[str], EvidenceRef] | None:
        for source in sources:
            match = pattern.search(source.text)
            if match is not None:
                return match, source.evidence
        return None

    async def generate_structured(
        self,
        request: StructuredLLMRequest[StructuredOutput],
    ) -> LLMResult[StructuredOutput]:
        if request.response_model is ThermalOptimizationDecision:
            return self._generate_thermal_decision(request)
        if request.response_model is not EngineeringBrief:
            raise InvalidLLMOutput()

        started_at = perf_counter()
        try:
            context = cast(dict[str, object], json.loads(request.user_prompt))
        except (json.JSONDecodeError, TypeError) as error:
            raise InvalidLLMOutput() from error

        sources = self._source_texts(context)
        combined_text = "\n".join(source.text for source in sources)
        power_match = self._find(sources, _POWER_PATTERN)
        ambient_match = self._find(sources, _AMBIENT_PATTERN)
        envelope_match = self._find(sources, _ENVELOPE_PATTERN)

        heat_sources = (
            [
                HeatSource(
                    name="主要热源",
                    power_w=float(power_match[0].group(1)),
                    evidence=[power_match[1]],
                    confidence=1,
                )
            ]
            if power_match
            else []
        )
        environment = (
            OperatingEnvironment(
                ambient_temp_c=float(ambient_match[0].group(1)),
                evidence=[ambient_match[1]],
                confidence=1,
            )
            if ambient_match
            else None
        )
        envelope = (
            Envelope(
                width_mm=float(envelope_match[0].group(1)),
                height_mm=float(envelope_match[0].group(2)),
                depth_mm=float(envelope_match[0].group(3)),
                evidence=[envelope_match[1]],
                confidence=1,
            )
            if envelope_match
            else None
        )
        brief = EngineeringBrief(
            project_title="ThermalForge 本地工程摘要",
            heat_sources=heat_sources,
            environment=environment,
            envelope=envelope,
            mounting_constraints=(
                ["保持原厂孔位"] if "保持原厂孔位" in combined_text else []
            ),
            required_features=(
                ["外壳可拆卸"] if "可拆卸" in combined_text else []
            ),
            overall_confidence=(
                1 if heat_sources and environment and envelope else 0.5
            ),
        )
        value = cast(StructuredOutput, brief)
        return LLMResult(
            value=value,
            provider="fixture",
            model="deterministic-engineering-brief-v1",
            request_id=None,
            input_tokens=max(1, len(request.user_prompt) // 4),
            output_tokens=max(1, len(brief.model_dump_json()) // 4),
            latency_ms=round((perf_counter() - started_at) * 1000),
        )

    @staticmethod
    def _generate_thermal_decision(
        request: StructuredLLMRequest[StructuredOutput],
    ) -> LLMResult[StructuredOutput]:
        started_at = perf_counter()
        try:
            context = cast(dict[str, object], json.loads(request.user_prompt))
            candidates = cast(
                list[dict[str, object]],
                context.get("compliant_candidates") or [],
            )
            selected = candidates[0]
            solution = cast(dict[str, object], selected["solution"])
            solution_id = str(solution["id"])
            materials = [
                str(value)
                for value in cast(list[object], solution.get("materials") or [])
            ]
            geometry_anchors = [
                str(value)
                for value in cast(
                    list[object],
                    solution.get("geometry_anchors") or [],
                )
            ]
            manufacturing_methods = [
                str(value)
                for value in cast(
                    list[object],
                    solution.get("manufacturing_methods") or [],
                )
            ]
        except (
            json.JSONDecodeError,
            KeyError,
            IndexError,
            TypeError,
        ) as error:
            raise InvalidLLMOutput() from error

        decision = ThermalOptimizationDecision(
            selected_solution_id=solution_id,
            rationale="该有效候选兼顾热扩散、结构兼容性和维护需求。",
            heat_transfer_path=["热源壳体", "导热界面", "外置扩散结构", "环境空气"],
            material_recommendations=materials or ["待确认材料"],
            geometry_anchors=geometry_anchors or ["热源安装面"],
            manufacturing_recommendations=(
                manufacturing_methods or ["可拆卸装配"]
            ),
            component_explanations=[
                ComponentExplanation(
                    component_id="thermal-interface",
                    name="导热界面",
                    explanation="把热流从原始壳体稳定传递到外置扩散结构。",
                ),
                ComponentExplanation(
                    component_id="spreader-shell",
                    name="扩散外壳",
                    explanation="扩散局部热点并增加空气侧换热面积。",
                ),
            ],
            risks=[
                DesignRisk(
                    source="thermal_analysis",
                    description="工程估算尚未通过样机曲线校准。",
                    impact="high",
                    recommended_action="冻结制造方案前完成样机温升复测。",
                )
            ],
            unverified_items=["接触热阻", "动态干涉"],
            requires_human_confirmation=True,
        )
        value = cast(StructuredOutput, decision)
        return LLMResult(
            value=value,
            provider="fixture",
            model="deterministic-thermal-optimization-v1",
            request_id=None,
            input_tokens=max(1, len(request.user_prompt) // 4),
            output_tokens=max(1, len(decision.model_dump_json()) // 4),
            latency_ms=round((perf_counter() - started_at) * 1000),
        )
