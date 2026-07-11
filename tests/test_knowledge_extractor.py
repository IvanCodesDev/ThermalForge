"""特性二：PDF 预提取单元测试（OQ7 低置信 needs_review / pypdf 缺失兜底）。"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.knowledge.extractor import ExtractedMotor, PdfExtractor
from core.knowledge.library import KnowledgeLibrary

SAMPLE = """
Motor Datasheet
Rated Power 50 W
Rated Voltage 48 V
Rated Speed 3000 rpm
Efficiency 85%
"""


def test_parse_motor_pure():
    extractor = PdfExtractor()
    motor = extractor.parse_motor(SAMPLE)
    assert isinstance(motor, ExtractedMotor)
    assert motor.rated_power_w == 50.0
    assert motor.rated_voltage_v == 48.0
    assert motor.rated_speed_rpm == 3000.0
    assert motor.efficiency == 85.0
    assert motor.confidence == 1.0


def test_parse_motor_empty_text():
    extractor = PdfExtractor()
    motor = extractor.parse_motor("no relevant fields here")
    assert motor.rated_power_w is None
    assert motor.confidence == 0.0


def test_extract_fallback_when_pypdf_missing(tmp_path, monkeypatch):
    # 强制走兜底分支（即便未来环境安装了 pypdf 也保证可复现）
    monkeypatch.setattr("core.knowledge.extractor._HAS_PYPDF", False)
    pdf = tmp_path / "datasheet.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake binary content")
    result = PdfExtractor().extract(pdf)
    assert result.status == "needs_review"
    assert "pypdf" in result.note.lower()
    assert result.extracted_json == "{}"


def test_extract_and_store_idempotent(tmp_path):
    pdf = tmp_path / "datasheet.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake binary content")
    library = KnowledgeLibrary(tmp_path / "kb.db")
    extractor = PdfExtractor()
    d1 = extractor.extract_and_store(pdf, library)
    d2 = extractor.extract_and_store(pdf, library)
    assert d1.content_hash == d2.content_hash
    assert len(library.search_by_keyword(pdf.name)) == 1
