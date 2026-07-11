"""PDF 预提取器（特性二）。

设计目标：优先使用 ``pypdf`` 抽取文本 → 套 ``MotorDatasheetTemplate`` /
``RobotArmSpecTemplate`` → 幂等入库（OQ7）。``pypdf`` 为可选依赖；若缺失，
则**仅登记文件名 + status=needs_review**，不解析二进制流（PDF 为二进制，
标准库无法可靠解码），并在结果中明确标注（OQ7 兜底）。

文本解析为启发式正则；字段置信低于阈值时整体标记 ``needs_review``。
所有入库以 ``content_hash``（文件 SHA-256）作为幂等键。
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.knowledge.library import DocEntry, KnowledgeLibrary, sha256_hex
from core.knowledge.templates import (
    MaterialSpecTemplate,
    MotorDatasheetTemplate,
    RobotArmSpecTemplate,
)

try:  # pypdf 为可选依赖
    import pypdf  # type: ignore

    _HAS_PYPDF = True
except Exception:  # pragma: no cover - 取决于运行环境是否安装 pypdf
    pypdf = None  # type: ignore
    _HAS_PYPDF = False

CONFIDENCE_THRESHOLD = 0.5


class ExtractedMotor(BaseModel):
    """抽取出的电机字段（中间产物）。"""

    model_config = ConfigDict(extra="forbid")

    motor_type: str = "BLDC"
    rated_power_w: float | None = None
    rated_voltage_v: float | None = None
    rated_speed_rpm: float | None = None
    efficiency: float | None = None
    confidence: float = 0.0


class DocExtractionResult(BaseModel):
    """一次 PDF 抽取的结果（可直接序列化 / 入库）。"""

    model_config = ConfigDict(extra="forbid")

    doc_id: str
    filename: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: str
    source_id: str
    extracted_json: str
    note: str = ""


class PdfExtractor:
    """从 PDF 抽取电机/机械臂/材料规格并映射到模板。"""

    def __init__(self) -> None:
        self.available: bool = _HAS_PYPDF

    # ----- 公共 API -----

    def extract(self, path: Path) -> DocExtractionResult:
        """抽取单个 PDF。

        pypdf 缺失时退化为仅登记文件名（OQ7 兜底），``status="needs_review"``。
        """
        path = Path(path)
        raw = path.read_bytes()
        content_hash = sha256_hex(raw)
        doc_id = f"kb-doc-{content_hash[:16]}"

        if not self.available:
            return DocExtractionResult(
                doc_id=doc_id,
                filename=path.name,
                content_hash=content_hash,
                status="needs_review",
                source_id=f"doc:{doc_id}",
                extracted_json="{}",
                note="pypdf 未安装：仅登记文件名，未解析 PDF 内容（OQ7 兜底）。",
            )

        text = self._extract_text(path)
        motor = self.parse_motor(text)
        payload: dict[str, Any] = {
            "motor": motor.model_dump(exclude={"confidence"}),
            "robot_arm": self.parse_robot_arm(text).model_dump(exclude_none=True),
            "material": self.parse_material(text).model_dump(exclude_none=True),
        }
        status = "extracted" if motor.confidence >= CONFIDENCE_THRESHOLD else "needs_review"
        keyword = " ".join(
            str(v) for v in [motor.motor_type, motor.rated_power_w, motor.rated_voltage_v]
            if v is not None
        )
        note = "" if status == "extracted" else "部分字段低置信，标记为 needs_review（OQ7）。"
        return DocExtractionResult(
            doc_id=doc_id,
            filename=path.name,
            content_hash=content_hash,
            status=status,
            source_id=f"doc:{doc_id}",
            extracted_json=_dump_json(payload),
            note=note + f" keyword={keyword!r}",
        )

    def extract_and_store(self, path: Path, library: KnowledgeLibrary) -> DocEntry:
        """抽取并将结果幂等入库，返回存储后的 DocEntry。"""
        result = self.extract(path)
        entry = DocEntry(
            doc_id=result.doc_id,
            filename=result.filename,
            content_hash=result.content_hash,
            status=result.status,
            extracted_json=result.extracted_json,
            keyword=result.filename,
        )
        return library.upsert_doc(entry)

    # ----- 文本抽取 -----

    def _extract_text(self, path: Path) -> str:
        if pypdf is None:
            return ""
        reader = pypdf.PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages:
            try:
                parts.append(page.extract_text() or "")
            except Exception:  # pragma: no cover - 个别页面解析异常不影响整体
                pass
        return "\n".join(parts)

    # ----- 字段解析（纯函数，便于单测）-----

    def parse_motor(self, text: str) -> ExtractedMotor:
        rated_power_w = self._first_number(
            text, [r"rated\s*power[^\d]*?([\d.,]+)\s*w", r"power[^\d]*?([\d.,]+)\s*w"]
        )
        rated_voltage_v = self._first_number(
            text, [r"rated\s*voltage[^\d]*?([\d.,]+)\s*v", r"voltage[^\d]*?([\d.,]+)\s*v"]
        )
        rated_speed_rpm = self._first_number(
            text, [r"rated\s*speed[^\d]*?([\d.,]+)\s*rpm", r"speed[^\d]*?([\d.,]+)\s*rpm"]
        )
        efficiency = self._first_number(text, [r"efficiency[^\d]*?([\d.,]+)\s*%"])
        found = [rated_power_w, rated_voltage_v, rated_speed_rpm, efficiency]
        confidence = sum(1 for item in found if item is not None) / len(found)
        return ExtractedMotor(
            rated_power_w=rated_power_w,
            rated_voltage_v=rated_voltage_v,
            rated_speed_rpm=rated_speed_rpm,
            efficiency=efficiency,
            confidence=confidence,
        )

    def parse_robot_arm(self, text: str) -> RobotArmSpecTemplate:
        dof = self._first_int(text, [r"(\d+)\s*[- ]?dof", r"degrees\s*of\s*freedom[^\d]*?(\d+)"])
        reach_mm = self._first_number(text, [r"reach[^\d]*?([\d.,]+)\s*mm"])
        payload_kg = self._first_number(text, [r"payload[^\d]*?([\d.,]+)\s*kg"])
        return RobotArmSpecTemplate(dof=dof, reach_mm=reach_mm, payload_kg=payload_kg)

    def parse_material(self, text: str) -> MaterialSpecTemplate:
        name = self._first_text(text, [r"material\s*[:=]\s*([A-Za-z0-9 ]+?)(?:\n|,)"])
        density = self._first_number(text, [r"density[^\d]*?([\d.,]+)\s*kg/m3"])
        k = self._first_number(text, [r"thermal\s*conductivity[^\d]*?([\d.,]+)\s*W/mK"])
        cp = self._first_number(text, [r"specific\s*heat[^\d]*?([\d.,]+)\s*J/kgK"])
        e = self._first_number(text, [r"young'?s\s*modulus[^\d]*?([\d.,]+)\s*Pa"])
        return MaterialSpecTemplate(
            name=name or "", density_kg_m3=density, thermal_conductivity_w_mk=k,
            specific_heat_j_kgk=cp, youngs_modulus_pa=e,
        )

    # ----- 正则辅助 -----

    @staticmethod
    def _first_number(text: str, patterns: list[str]) -> float | None:
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                try:
                    return float(match.group(1).replace(",", ""))
                except (ValueError, AttributeError):
                    return None
        return None

    @staticmethod
    def _first_int(text: str, patterns: list[str]) -> int | None:
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                try:
                    return int(float(match.group(1).replace(",", "")))
                except (ValueError, AttributeError):
                    return None
        return None

    @staticmethod
    def _first_text(text: str, patterns: list[str]) -> str | None:
        for pat in patterns:
            match = re.search(pat, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return None


def _dump_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True)
