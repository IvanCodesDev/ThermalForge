"""特性二：知识库 sqlite 封装单元测试（OQ2 索引 / content_hash 幂等 / 三类检索）。"""
from __future__ import annotations

import json

import pytest

from core.knowledge.defaults import BldcDefaults, DEFAULT_MATERIALS
from core.knowledge.library import DocEntry, KnowledgeLibrary, MaterialEntry, MotorEntry, sha256_hex


@pytest.fixture
def lib(tmp_path):
    return KnowledgeLibrary(tmp_path / "kb.db")


def _motor_entry() -> MotorEntry:
    params = json.dumps(BldcDefaults.DEFAULT_BLDC_MOTOR, sort_keys=True)
    h = sha256_hex(params)
    return MotorEntry(
        entry_id=f"kb-motor-{h[:16]}",
        motor_type="BLDC",
        params_json=params,
        source_id="default:bldc",
        content_hash=h,
    )


def _material_entry(material_id: str) -> MaterialEntry:
    props = json.dumps(DEFAULT_MATERIALS[material_id], sort_keys=True)
    h = sha256_hex(props)
    return MaterialEntry(
        material_id=DEFAULT_MATERIALS[material_id]["material_id"],
        name=DEFAULT_MATERIALS[material_id]["name"],
        properties_json=props,
        source_id="default:material",
        content_hash=h,
    )


def test_motor_upsert_idempotent(lib):
    entry = _motor_entry()
    r1 = lib.upsert_motor(entry)
    r2 = lib.upsert_motor(entry)
    assert r1.content_hash == r2.content_hash
    assert len(lib.search_by_motor_type("BLDC")) == 1


def test_material_upsert_idempotent(lib):
    entry = _material_entry("al")
    lib.upsert_material(entry)
    lib.upsert_material(entry)
    rows = lib.search_by_material("al")
    assert len(rows) == 1
    assert rows[0].name == "Aluminum"


def test_search_by_material_name_and_id(lib):
    lib.upsert_material(_material_entry("steel"))
    assert len(lib.search_by_material("steel")) == 1
    assert len(lib.search_by_material("Steel")) == 1
    assert len(lib.search_by_material("nonexistent")) == 0


def test_doc_upsert_idempotent_and_keyword(lib, tmp_path):
    doc = tmp_path / "datasheet.pdf"
    doc.write_bytes(b"%PDF-1.4 fake content")
    h = sha256_hex(doc.read_bytes())
    entry = DocEntry(
        doc_id=f"kb-doc-{h[:16]}",
        filename="datasheet.pdf",
        content_hash=h,
        status="needs_review",
        extracted_json="{}",
        keyword="datasheet.pdf",
    )
    lib.upsert_doc(entry)
    lib.upsert_doc(entry)
    rows = lib.search_by_keyword("datasheet.pdf")
    assert len(rows) == 1
    assert rows[0].status == "needs_review"
