"""确定性 V251 renderer；默认不执行 SpaceClaim。"""
from __future__ import annotations
import json
from pathlib import Path
from core.models.spaceclaim_contract import SpaceClaimHandoffContract

class SpaceClaimV251Renderer:
    """将已验证契约渲染为固定、无 LLM 脚本文本的 SpaceClaim 脚本。"""
    def render(self, handoff: SpaceClaimHandoffContract) -> str:
        payload = json.dumps(handoff.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        lines = ["from SpaceClaim.Api.V251 import *", "import json", f"HANDOFF = json.loads({payload!r})", "ClearAll()"]
        for joint in handoff.joints:
            lines.append(f"# joint:{joint.id} outer={joint.outer_radius_mm} inner={joint.inner_radius_mm}")
        lines.append("# Geometry operations are executed only by the authorized V251 host adapter.")
        return "\n".join(lines) + "\n"

    def write(self, handoff: SpaceClaimHandoffContract, workspace: Path) -> Path:
        workspace = workspace.resolve()
        workspace.mkdir(parents=True, exist_ok=True)
        target = (workspace / f"{handoff.id}.py").resolve()
        if workspace not in target.parents:
            raise ValueError("脚本路径逃逸隔离 workspace")
        target.write_text(self.render(handoff), encoding="utf-8")
        return target
