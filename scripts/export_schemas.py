"""
导出参数中枢契约文件到 data/schemas/（满足 annotation-strategy-v0.1.md §6 GitHub 上传要求）。

产出：
  leaf_vein.schema.json   叶脉结构几何参数 JSON Schema
  channel.schema.json     流道结构几何参数 JSON Schema
  flat.schema.json        平板基线参数 JSON Schema
  user_input.schema.json  上游输入层 JSON Schema
  library_entry.schema.json 库条目 JSON Schema
  constraint_vector.spec.json  用户意图约束向量 23 维规格说明

运行：venv python scripts/export_schemas.py
"""
from __future__ import annotations

import sys
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.models.schema import RANGE_SPECS, STRUCTURE_CLASSES
from core.models.user_input import (
    UserInput, DEVICE_TYPES, MATERIALS, MANUFACTURING, MEDIUM,
)
OUT = ROOT / "data" / "schemas"
OUT.mkdir(parents=True, exist_ok=True)

JSON_SCHEMA_VER = "https://json-schema.org/draft/2020-12/schema"


def _field_to_jsonschema(name: str, spec):
    """spec: (min,max) 或 [enum...]"""
    if isinstance(spec, (list, tuple)) and all(isinstance(x, str) for x in spec):
        return {"type": "string", "enum": list(spec), "title": name}
    lo, hi = spec
    return {"type": "number", "minimum": lo, "maximum": hi, "title": name}


def export_structure_schemas():
    for stype, specs in RANGE_SPECS.items():
        props = {}
        required = []
        for fname, fspec in specs.items():
            props[fname] = _field_to_jsonschema(fname, fspec)
            required.append(fname)
        schema = {
            "$schema": JSON_SCHEMA_VER,
            "$id": f"https://thermalforge.dev/schemas/{stype}.schema.json",
            "title": f"ThermalForge {stype} 结构几何参数",
            "type": "object",
            "properties": props,
            "required": required,
            "additionalProperties": False,
        }
        (OUT / f"{stype}.schema.json").write_text(
            json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"  ✓ {stype}.schema.json ({len(props)} 字段)")


def export_user_input_schema():
    props = {
        "device_type": {"type": "string", "enum": list(DEVICE_TYPES), "title": "器件类型"},
        "dimensions": {
            "type": "object",
            "title": "尺寸(mm)",
            "properties": {
                "length_mm": {"type": "number"}, "width_mm": {"type": "number"},
                "height_mm": {"type": "number"}, "outer_dia_mm": {"type": "number"},
                "inner_dia_mm": {"type": "number"},
            },
            "additionalProperties": False,
        },
        "power_w": {"type": "number", "minimum": 0.1, "title": "功耗 W"},
        "max_temp_c": {"type": "number", "minimum": 1, "maximum": 300, "title": "允许最高温度 ℃"},
        "material": {"type": "string", "enum": list(MATERIALS), "title": "材料"},
        "has_fan": {"type": "boolean", "title": "是否强制风冷"},
        "max_weight_g": {"type": "number", "minimum": 0.1, "title": "重量上限 g"},
        "manufacturing": {"type": "string", "enum": list(MANUFACTURING), "title": "制造方式"},
        "ambient_temp_c": {"type": "number", "minimum": -40, "maximum": 80, "title": "环境温度 ℃"},
    }
    schema = {
        "$schema": JSON_SCHEMA_VER,
        "$id": "https://thermalforge.dev/schemas/user_input.schema.json",
        "title": "ThermalForge 上游输入层（UserInput）",
        "type": "object",
        "properties": props,
        "required": ["device_type", "power_w", "max_temp_c", "material", "max_weight_g"],
        "additionalProperties": False,
    }
    (OUT / "user_input.schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  ✓ user_input.schema.json ({len(props)} 字段)")


def export_library_entry_schema():
    schema = {
        "$schema": JSON_SCHEMA_VER,
        "$id": "https://thermalforge.dev/schemas/library_entry.schema.json",
        "title": "ThermalForge 库条目（LibraryEntry · §2.5）",
        "type": "object",
        "properties": {
            "case_id": {"type": "string"},
            "source": {"type": "string"},
            "device_context": {"$ref": "user_input.schema.json"},
            "structure": {"type": "object", "description": "结构几何参数（含 structure_type）"},
            "model_path": {"type": "string"},
            "preview_img": {"type": "string"},
            "perf_notes": {"type": "string"},
            "constraint_vector": {"type": "array", "items": {"type": "number"}},
        },
        "required": ["case_id", "source", "device_context", "structure"],
        "additionalProperties": False,
    }
    (OUT / "library_entry.schema.json").write_text(
        json.dumps(schema, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("  ✓ library_entry.schema.json")


def export_constraint_vector_spec():
    spec = {
        "title": "ThermalForge 用户意图约束向量（constraint_vector）",
        "dimension": len(UserInput.vector_spec()),
        "space": "user_intent",
        "note": "UserInput.to_vector() 与 LibraryEntry.constraint_vector 同空间，用于最近邻检索",
        "components": UserInput.vector_spec(),
    }
    (OUT / "constraint_vector.spec.json").write_text(
        json.dumps(spec, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"  ✓ constraint_vector.spec.json ({spec['dimension']} 维)")


def main():
    print(f"导出参数中枢契约 → {OUT}")
    export_structure_schemas()
    export_user_input_schema()
    export_library_entry_schema()
    export_constraint_vector_spec()
    print("完成。")


if __name__ == "__main__":
    main()
