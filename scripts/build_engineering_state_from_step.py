"""STEP → EngineeringState 构建驱动脚本（特性一 · 第一脚本）。

流程：``StepReader.parse`` → ``StepToEngineeringStateBuilder.build`` →
落盘 ``outputs/<project_id>/engineering-state.json``（并回读做
``EngineeringState.model_validate_json`` 自检）。

说明：为保持构建产物可复现、不耦合运行时存储，本脚本直接将构建出的
EngineeringState 序列化落盘（而非经由 ``EngineeringStateService`` 的 DB 存储）；
这与系统设计的「构建出 revision=1 的 EngineeringState」目标一致。

用法：
    python scripts/build_engineering_state_from_step.py [STEP路径] [project_id]
默认 STEP 路径：C:/Users/llwxy/Downloads/机械臂/IKI1602.STEP
默认 project_id：iki1602
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.config import PROJECT_ROOT  # noqa: E402
from core.engine.step_reader import StepReader  # noqa: E402
from core.models.engineering_state import EngineeringState  # noqa: E402
from core.services.engineering_state_from_step import (  # noqa: E402
    StepToEngineeringStateBuilder,
)

DEFAULT_STEP = Path(r"C:/Users/llwxy/Downloads/机械臂/IKI1602.STEP")


def main(argv: list[str]) -> Path:
    step_path = Path(argv[1]) if len(argv) > 1 else DEFAULT_STEP
    project_id = argv[2] if len(argv) > 2 else "iki1602"

    if not step_path.exists():
        print(f"[ERROR] STEP 文件不存在: {step_path}", file=sys.stderr)
        raise SystemExit(1)

    result = StepReader().parse(step_path)
    state = StepToEngineeringStateBuilder().build(project_id, result, step_path)

    out_dir = PROJECT_ROOT / "outputs" / project_id
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "engineering-state.json"
    out_path.write_text(
        json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 自检：回读并校验 extra=forbid
    EngineeringState.model_validate_json(out_path.read_text(encoding="utf-8"))

    print(f"已生成：{out_path}")
    rounded_bbox = tuple(round(v, 2) for v in result.bbox_mm)
    print(f"  bbox_mm={rounded_bbox}")
    print(
        f"  part_count={result.part_count}  cylinders={len(result.cylinders)}"
    )
    print(
        f"  joints={len(state.joints)}  materials={len(state.materials)}"
        f"  thermal_loads={len(state.thermal_loads)}"
        f"  operating_cases={len(state.operating_cases)}"
        f"  unresolved={len(state.unresolved)}"
    )
    return out_path


if __name__ == "__main__":
    main(sys.argv)
