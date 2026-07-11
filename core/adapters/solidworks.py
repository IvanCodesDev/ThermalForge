"""SolidWorks 优化执行适配器。

编排脚本渲染与 SolidWorksRunner 执行，返回结构化结果。
"""
from __future__ import annotations

import json
from pathlib import Path

from core.engine.solidworks_runner import SolidWorksRunner
from core.engine.solidworks_script import SolidWorksScriptRenderer
from core.models.optimization import (
    SolidWorksExecutionResult,
    SolidWorksOptimizationContract,
)


class SolidWorksAdapter:
    """将优化契约渲染为 COM 脚本并执行，返回产物路径。"""

    def __init__(self, runner: SolidWorksRunner | None = None) -> None:
        self.runner = runner or SolidWorksRunner()
        self.renderer = SolidWorksScriptRenderer()

    @property
    def available(self) -> bool:
        return self.runner.available

    def preflight(self, timeout: float = 60.0) -> dict:
        """委托给 runner 的 preflight。"""
        return self.runner.preflight(timeout=timeout)

    def execute(self, contract: SolidWorksOptimizationContract) -> SolidWorksExecutionResult:
        """渲染脚本 → 执行 → 解析产物 → 返回结果。"""
        if not self.runner.available:
            return SolidWorksExecutionResult(
                status="skipped",
                error="SolidWorks 未安装，跳过执行",
                metadata={"reason": "not_available"},
            )

        workspace = Path(contract.output_plan.workspace_dir)
        workspace.mkdir(parents=True, exist_ok=True)
        script_path = self.renderer.write(contract, workspace)

        run_result = self.runner.run(str(script_path))

        if run_result.get("status") != "ok":
            return SolidWorksExecutionResult(
                status=run_result.get("status", "error"),
                error=run_result.get("reason") or run_result.get("error"),
                metadata={"run_result": run_result},
            )

        # 解析 manifest
        manifest_path = run_result.get("manifest_path")
        manifest: dict = {}
        if manifest_path and Path(manifest_path).exists():
            try:
                manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                manifest = {}

        return SolidWorksExecutionResult(
            status="ok",
            step_path=manifest.get("step_path") or run_result.get("step_path"),
            stl_path=manifest.get("stl_path") or run_result.get("stl_path"),
            preview_paths=manifest.get("preview_paths", []),
            review_report_path=manifest.get("review_report_path"),
            manifest_path=manifest_path,
            metadata={**manifest, "run_result": {k: v for k, v in run_result.items() if k != "stdout"}},
        )
