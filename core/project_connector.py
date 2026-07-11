"""ThermalForge 项目连接器：文件、参数、CAD 执行与变化验证的统一入口。"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from core.engine.spaceclaim import SpaceClaimArtifact, create_candidate_artifact
from core.engine.spaceclaim_runner import SpaceClaimRunner
from core.models.cold_plate import ColdPlateParams


@dataclass(frozen=True)
class ConnectorConfig:
    project_root: Path
    output_dir: Path
    source_model_path: str = ""
    launch_mode: str = "explorer"
    license_feature: str = "disco_level1"
    timeout: float = 300.0


class ThermalForgeConnector:
    """项目级编排器。

    - 文件能力严格限制在 project_root 内；
    - 参数由 ColdPlateParams 校验；
    - CAD 执行复用 SpaceClaimRunner；
    - 变化验证比较参数哈希、派生几何、manifest 与 STEP 文件。
    """

    def __init__(
        self,
        project_root: str | Path,
        output_dir: str | Path = "data/connector_runs",
        source_model_path: str = "",
        launch_mode: str = "explorer",
        license_feature: str = "disco_level1",
        timeout: float = 300.0,
        runner: Optional[SpaceClaimRunner] = None,
    ):
        root = Path(project_root).resolve()
        if not root.is_dir():
            raise ValueError(f"项目根目录不存在: {root}")
        output = self._resolve_inside(root, output_dir)
        self.config = ConnectorConfig(
            project_root=root,
            output_dir=output,
            source_model_path=source_model_path,
            launch_mode=launch_mode,
            license_feature=license_feature,
            timeout=timeout,
        )
        self.runner = runner or SpaceClaimRunner(
            timeout=timeout,
            launch_mode=launch_mode,
            license_feature=license_feature,
        )

    @staticmethod
    def _resolve_inside(root: Path, relative_or_absolute: str | Path) -> Path:
        candidate = Path(relative_or_absolute)
        if not candidate.is_absolute():
            candidate = root / candidate
        resolved = candidate.resolve()
        try:
            resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(f"路径越过项目边界: {relative_or_absolute}") from exc
        return resolved

    def resolve(self, path: str | Path) -> Path:
        return self._resolve_inside(self.config.project_root, path)

    def status(self) -> Dict[str, Any]:
        return {
            "project_root": str(self.config.project_root),
            "output_dir": str(self.config.output_dir),
            "spaceclaim": {
                "available": self.runner.available,
                "executable": self.runner.executable,
                "api_version": self.runner.api_version,
                "launch_mode": self.runner.launch_mode,
                "license_feature": self.runner.license_feature,
            },
            "pipeline": [
                "project_files",
                "cold_plate_params",
                "spaceclaim_script",
                "spaceclaim_execution",
                "step_and_manifest",
                "parameter_change_verification",
            ],
        }

    def list_files(self, path: str = ".", patterns: Iterable[str] = ("*",), limit: int = 500) -> list[str]:
        base = self.resolve(path)
        if not base.is_dir():
            raise ValueError(f"不是目录: {path}")
        found: set[Path] = set()
        for pattern in patterns:
            found.update(p for p in base.rglob(pattern) if p.is_file())
        return [str(p.relative_to(self.config.project_root)) for p in sorted(found)[:limit]]

    def read_text(self, path: str, max_chars: int = 200_000) -> str:
        target = self.resolve(path)
        if not target.is_file():
            raise ValueError(f"文件不存在: {path}")
        text = target.read_text(encoding="utf-8")
        if len(text) > max_chars:
            raise ValueError(f"文件超过读取上限 {max_chars} 字符")
        return text

    def replace_text(self, path: str, old_text: str, new_text: str) -> Dict[str, Any]:
        """精确替换项目内文本；拒绝空匹配、多匹配和无变化操作。"""
        if not old_text or old_text == new_text:
            raise ValueError("old_text 必须非空且与 new_text 不同")
        target = self.resolve(path)
        text = target.read_text(encoding="utf-8")
        count = text.count(old_text)
        if count != 1:
            raise ValueError(f"精确替换要求唯一匹配，实际匹配 {count} 次")
        target.write_text(text.replace(old_text, new_text, 1), encoding="utf-8")
        return {"path": str(target.relative_to(self.config.project_root)), "replacements": 1}

    def create_model(
        self,
        params_data: Dict[str, Any],
        candidate_id: Optional[str] = None,
        execute: bool = True,
    ) -> Dict[str, Any]:
        params = ColdPlateParams.from_dict(params_data)
        cid = candidate_id or f"CP-{params.parameter_hash()[:12]}"
        artifact = create_candidate_artifact(
            params,
            self.config.output_dir,
            candidate_id=cid,
            source_model_path=self.config.source_model_path,
            api_version=self.runner.api_version,
        )
        result: Dict[str, Any] = {
            "params": params.to_dict(),
            "derived": params.derived(),
            "artifact": artifact.to_dict(),
            "execution": None,
        }
        if execute:
            result["execution"] = self.runner.run(artifact.script_path)
            result["manifest"] = self._read_manifest(artifact)
        return result

    @staticmethod
    def _read_manifest(artifact: SpaceClaimArtifact) -> Dict[str, Any]:
        path = Path(artifact.manifest_path)
        if not path.exists():
            return {}
        return json.loads(path.read_text(encoding="utf-8"))

    def verify_model_change(
        self,
        baseline_params: Dict[str, Any],
        changed_params: Dict[str, Any],
        execute: bool = True,
    ) -> Dict[str, Any]:
        baseline = self.create_model(baseline_params, "CP-CONNECTOR-BASE", execute=execute)
        changed = self.create_model(changed_params, "CP-CONNECTOR-CHANGED", execute=execute)

        base_p = ColdPlateParams.from_dict(baseline_params)
        changed_p = ColdPlateParams.from_dict(changed_params)
        derived_diff = {
            key: {"before": base_p.derived()[key], "after": changed_p.derived()[key]}
            for key in base_p.derived()
            if base_p.derived()[key] != changed_p.derived()[key]
        }
        step_changed = False
        base_step = Path(baseline["artifact"]["expected_step_path"])
        changed_step = Path(changed["artifact"]["expected_step_path"])
        if base_step.exists() and changed_step.exists():
            step_changed = base_step.read_bytes() != changed_step.read_bytes()

        checks = {
            "params_hash_changed": base_p.parameter_hash() != changed_p.parameter_hash(),
            "derived_geometry_changed": bool(derived_diff),
            "scripts_changed": Path(baseline["artifact"]["script_path"]).read_bytes()
            != Path(changed["artifact"]["script_path"]).read_bytes(),
            "baseline_execution_ok": (not execute) or baseline.get("execution", {}).get("status") == "ok",
            "changed_execution_ok": (not execute) or changed.get("execution", {}).get("status") == "ok",
            "step_changed": (not execute) or step_changed,
        }
        return {
            "ok": all(checks.values()),
            "checks": checks,
            "derived_diff": derived_diff,
            "baseline": baseline,
            "changed": changed,
        }

    def snapshot(self) -> Dict[str, Any]:
        return {
            "config": {
                **asdict(self.config),
                "project_root": str(self.config.project_root),
                "output_dir": str(self.config.output_dir),
            },
            "status": self.status(),
        }
