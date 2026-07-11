"""EngineeringState → SpaceClaim Handoff 构建驱动脚本（特性一 · 第二脚本）。

流程：读 ``outputs/<project_id>/engineering-state.json``（rev=1）→
``SpaceClaimHandoffCompiler.compile`` → 落盘
``outputs/<project_id>/spaceclaim-handoff.json``，并用既有
``SpaceClaimV251Renderer.write`` 生成 ``spaceclaim-handoff.py``。

用法：
    python scripts/build_spaceclaim_handoff.py [project_id]
默认 project_id：iki1602
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.adapters.spaceclaim_v251 import SpaceClaimV251Renderer  # noqa: E402
from core.config import PROJECT_ROOT  # noqa: E402
from core.models.engineering_state import EngineeringState  # noqa: E402
from core.models.spaceclaim_contract import SpaceClaimHandoffContract  # noqa: E402
from core.services.spaceclaim_handoff import SpaceClaimHandoffCompiler  # noqa: E402


def main(argv: list[str]) -> tuple[Path, Path]:
    project_id = argv[1] if len(argv) > 1 else "iki1602"
    out_dir = PROJECT_ROOT / "outputs" / project_id
    state_path = out_dir / "engineering-state.json"
    if not state_path.exists():
        print(
            f"[ERROR] 未找到 {state_path}，请先运行 build_engineering_state_from_step.py",
            file=sys.stderr,
        )
        raise SystemExit(1)

    state = EngineeringState.model_validate_json(state_path.read_text(encoding="utf-8"))
    contract = SpaceClaimHandoffCompiler().compile(state)

    handoff_path = out_dir / "spaceclaim-handoff.json"
    handoff_path.write_text(contract.model_dump_json(indent=2), encoding="utf-8")

    py_path = SpaceClaimV251Renderer().write(contract, out_dir)

    # 自检
    SpaceClaimHandoffContract.model_validate_json(handoff_path.read_text(encoding="utf-8"))

    print(f"已生成：{handoff_path}")
    print(f"已生成：{py_path}")
    print(
        f"  approval_status={contract.approval_status}  joints={len(contract.joints)}"
        f"  materials={len(contract.materials)}"
        f"  named_selections={len(contract.named_selections)}"
        f"  contacts={len(contract.contacts)}"
    )
    return handoff_path, py_path


if __name__ == "__main__":
    main(sys.argv)
