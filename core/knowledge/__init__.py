"""ThermalForge 知识库包：文档模板、默认目录、sqlite 知识库与 PDF 预提取。

零强制第三方依赖：仅依赖 pydantic（已安装）与 Python 标准库
（sqlite3 / hashlib / re / json / pathlib）。PDF 抽取为可选能力，
缺失 pypdf 时退化为"仅登记文件名 + needs_review"（见 OQ7）。
"""
from __future__ import annotations

from .templates import (
    MaterialSpecTemplate,
    MotorDatasheetTemplate,
    RobotArmSpecTemplate,
)
from .defaults import (
    BldcDefaults,
    DEFAULT_BLDC_MOTOR,
    DEFAULT_MATERIALS,
    MATERIAL_PROPERTY_KEYS,
)
from .library import (
    DocEntry,
    KnowledgeLibrary,
    MaterialEntry,
    MotorEntry,
    sha256_hex,
)
from .extractor import DocExtractionResult, PdfExtractor

__all__ = [
    "MaterialSpecTemplate",
    "MotorDatasheetTemplate",
    "RobotArmSpecTemplate",
    "BldcDefaults",
    "DEFAULT_BLDC_MOTOR",
    "DEFAULT_MATERIALS",
    "MATERIAL_PROPERTY_KEYS",
    "KnowledgeLibrary",
    "MotorEntry",
    "MaterialEntry",
    "DocEntry",
    "sha256_hex",
    "PdfExtractor",
    "DocExtractionResult",
]
