"""固化通用默认知识条目（特性二）。

将默认 BLDC 电机与默认材质表（al / steel）写入全局共享
``data/knowledge.db``。以 ``content_hash`` 作为幂等键，可重复执行：
重复运行不会新增重复行（OQ2 / 知识库可重复种子）。

用法：
    python scripts/seed_knowledge_base.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.knowledge.defaults import BldcDefaults, DEFAULT_MATERIALS  # noqa: E402
from core.knowledge.library import KnowledgeLibrary, MaterialEntry, MotorEntry, sha256_hex  # noqa: E402


def seed(library: KnowledgeLibrary | None = None) -> KnowledgeLibrary:
    library = library or KnowledgeLibrary()

    # 默认 BLDC 电机目录条目（证据：default:bldc）
    motor = BldcDefaults.DEFAULT_BLDC_MOTOR
    params_json = json.dumps(motor, ensure_ascii=False, sort_keys=True)
    motor_hash = sha256_hex(params_json)
    library.upsert_motor(
        MotorEntry(
            entry_id=f"kb-motor-{motor_hash[:16]}",
            motor_type=motor["motor_type"],
            params_json=params_json,
            source_id="default:bldc",
            content_hash=motor_hash,
        )
    )

    # 默认材质表（al / steel），证据：default:material
    for material_id, props in DEFAULT_MATERIALS.items():
        properties_json = json.dumps(props, ensure_ascii=False, sort_keys=True)
        material_hash = sha256_hex(properties_json)
        library.upsert_material(
            MaterialEntry(
                material_id=props["material_id"],
                name=props["name"],
                properties_json=properties_json,
                source_id="default:material",
                content_hash=material_hash,
            )
        )

    return library


if __name__ == "__main__":
    lib = seed()
    print(f"已生成知识库：{lib.db_path}")
    print(f"  motors(BLDC) = {len(lib.search_by_motor_type('BLDC'))}")
    print(f"  materials(al) = {len(lib.search_by_material('al'))}")
    print(f"  materials(steel) = {len(lib.search_by_material('steel'))}")
