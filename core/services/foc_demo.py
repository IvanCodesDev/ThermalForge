"""Repository and safety helpers for the reproducible FOC demo output."""
from __future__ import annotations

from dataclasses import asdict
import json
import os
from pathlib import Path
import tempfile
from typing import Any
from urllib.parse import quote, urlsplit, urlunsplit

from core.engine.foc_simulation import FocJointInput, simulate_foc_joint
from core.models.foc_demo import (
    FocDemoAsset,
    FocDemoDecision,
    FocDemoDesign,
    FocDemoHeatPath,
    FocDemoMeshStructure,
    FocDemoSnapshot,
    FocDemoStage,
    FocDemoThermal,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "foc_robot_arm_backend_output.json"
DEFAULT_ASSET_DIR = PROJECT_ROOT / "outputs" / "foc_robot_arm_assets"
DEFAULT_REASONING_PATH = PROJECT_ROOT / "outputs" / "foc_robot_arm_design_reasoning.json"

_SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "client_secret",
    "password",
    "private_key",
    "refresh_token",
    "secret",
    "subscription_key",
    "access_token",
}
_ASSET_ROUTE = "/api/v1/foc-demo/assets"
_MEDIA_TYPES = {
    ".glb": "model/gltf-binary",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}


class AssetNotFoundError(FileNotFoundError):
    """Raised when a requested demo asset is not in the local whitelist."""


def _is_sensitive_key(key: object) -> bool:
    normalized = str(key).strip().lower().replace("-", "_")
    return normalized in _SENSITIVE_KEYS or normalized.endswith("_api_key")


def _strip_url_query(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme.lower() not in {"http", "https"} or not parts.query:
        return value
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", parts.fragment))


def redact_backend_output(value: Any) -> Any:
    """Return a recursively copied output without credentials or URL queries."""
    if isinstance(value, dict):
        return {
            key: redact_backend_output(item)
            for key, item in value.items()
            if not _is_sensitive_key(key)
        }
    if isinstance(value, list):
        return [redact_backend_output(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_backend_output(item) for item in value)
    if isinstance(value, str):
        return _strip_url_query(value)
    return value


class FocDemoRepository:
    def __init__(
        self,
        output_path: str | Path = DEFAULT_OUTPUT_PATH,
        asset_dir: str | Path = DEFAULT_ASSET_DIR,
        reasoning_path: str | Path = DEFAULT_REASONING_PATH,
    ) -> None:
        self.output_path = Path(output_path)
        self.asset_dir = Path(asset_dir)
        self.reasoning_path = Path(reasoning_path)

    def raw(self) -> dict[str, Any]:
        return redact_backend_output(self._read_json(self.output_path))

    def snapshot(self) -> FocDemoSnapshot:
        data = self.raw()
        thermal_data = data.get("screening_evaluation") or {}
        mesh_data = data.get("bang_glb_structure") or {}
        assets = self._discover_assets(data)
        thermal = FocDemoThermal(
            state=thermal_data.get("state"),
            fidelity=str(thermal_data.get("fidelity") or "screening"),
            backend=str(thermal_data.get("backend") or "lumped_estimator"),
            not_cfd=True,
            metrics=thermal_data.get("metrics") or {},
            recommended_parameters=thermal_data.get("recommended_parameters") or {},
            geometry=thermal_data.get("geometry") or {},
            limitations=list(thermal_data.get("limitations") or []),
        )
        mesh = FocDemoMeshStructure.model_validate({**mesh_data, "manufacturable_cad": False})
        design = self._load_design(data, thermal)
        limitations = self._limitations(data, thermal)
        return FocDemoSnapshot(
            generated_at=data.get("generated_at"),
            scenario=str(data.get("scenario") or "FOC robot arm thermal design"),
            engineering_input=str(data.get("engineering_input") or ""),
            brief=data.get("confirmed_brief") or data.get("engineering_brief") or {},
            configured_models=data.get("configured_models") or {},
            foc_simulation=asdict(simulate_foc_joint(FocJointInput())),
            thermal=thermal,
            assets=assets,
            mesh_structure=mesh,
            stages=self._stages(data, assets, mesh),
            design=design,
            limitations=limitations,
        )

    def persist_design(self, payload: dict[str, Any]) -> FocDemoDesign:
        """Validate, sanitize, and atomically persist a model decision ledger."""
        safe_payload = redact_backend_output(payload)
        if not isinstance(safe_payload, dict):
            raise ValueError("FOC design reasoning must be a JSON object")

        design = FocDemoDesign.model_validate(
            {**safe_payload, "source": "persisted_model"}
        )
        serialized = json.dumps(
            design.model_dump(mode="json"),
            ensure_ascii=False,
            indent=2,
        )

        self.reasoning_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self.reasoning_path.parent,
                prefix=f".{self.reasoning_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temporary_path = Path(handle.name)
                handle.write(serialized)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self.reasoning_path)
            temporary_path = None
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)

        return design

    def resolve_asset(self, name: str) -> Path:
        if not name or Path(name).name != name or "/" in name or "\\" in name:
            raise AssetNotFoundError(name)
        allowed = {asset.filename for asset in self._discover_assets(self.raw())}
        if name not in allowed:
            raise AssetNotFoundError(name)
        root = self.asset_dir.resolve()
        candidate = (root / name).resolve()
        if candidate.parent != root or not candidate.is_file():
            raise AssetNotFoundError(name)
        return candidate

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any]:
        payload = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError(f"Expected a JSON object in {path}")
        return payload

    def _discover_assets(self, data: dict[str, Any]) -> list[FocDemoAsset]:
        discovered: dict[str, FocDemoAsset] = {}
        calls = data.get("external_calls") or {}
        for call_name, provider in (("hyper3d_rodin", "rodin"), ("hyper3d_bang", "bang")):
            call = calls.get(call_name) or {}
            for item in call.get("local_assets") or []:
                if not isinstance(item, dict):
                    continue
                local_path = str(item.get("local_path") or item.get("name") or "")
                filename = local_path.replace("\\", "/").rsplit("/", 1)[-1]
                suffix = Path(filename).suffix.lower()
                identity = self._asset_identity(provider, suffix)
                candidate = self.asset_dir / filename
                if identity is None or not candidate.is_file():
                    continue
                asset_id, kind = identity
                discovered.setdefault(
                    asset_id,
                    FocDemoAsset(
                        id=asset_id,
                        provider=provider,
                        kind=kind,
                        filename=filename,
                        url=f"{_ASSET_ROUTE}/{quote(filename)}",
                        media_type=_MEDIA_TYPES[suffix],
                        size_bytes=candidate.stat().st_size,
                    ),
                )
        order = {"rodin-model": 0, "bang-model": 1, "rodin-preview": 2, "rodin-render": 3}
        return sorted(discovered.values(), key=lambda asset: order.get(asset.id, 99))

    @staticmethod
    def _asset_identity(provider: str, suffix: str) -> tuple[str, str] | None:
        if suffix == ".glb":
            return (f"{provider}-model", "model")
        if provider == "rodin" and suffix == ".webp":
            return ("rodin-preview", "preview")
        if provider == "rodin" and suffix in {".jpg", ".jpeg"}:
            return ("rodin-render", "render")
        return None

    def _load_design(self, data: dict[str, Any], thermal: FocDemoThermal) -> FocDemoDesign:
        if self.reasoning_path.is_file():
            payload = redact_backend_output(self._read_json(self.reasoning_path))
            return FocDemoDesign.model_validate({**payload, "source": "persisted_model"})
        hotspot = thermal.metrics.get("t_hotspot_c")
        limit = thermal.metrics.get("t_limit_c")
        evidence = ["持续热耗散按工程输入 120 W"]
        if hotspot is not None:
            evidence.append(f"筛选估算热点温度 {hotspot} °C")
        if limit is not None:
            evidence.append(f"器件温度上限 {limit} °C")
        return FocDemoDesign(
            architecture="双热源、双传导路径；被动散热优先，并保留液冷升级接口。",
            heat_paths=[
                FocDemoHeatPath(
                    name="FOC 功率器件热路径",
                    route=["MOSFET", "导热垫", "驱动器底板", "6061 铝外壳"],
                    why="缩短高热流密度功率器件到外壳的界面路径。",
                    evidence=evidence,
                    validation="建立双热源热网络，并以 CFD/实测复核界面温升。",
                ),
                FocDemoHeatPath(
                    name="电机定子热路径",
                    route=["PMSM 定子", "导热环", "6061 铝外壳", "外部散热肋"],
                    why="让电机铜耗绕过减速器，直接扩散到关节壳体。",
                    evidence=["无独立风扇", "外壳一体化扩热肋"],
                    validation="布置绕组与壳体热电偶，验证接触热阻。",
                ),
            ],
            decisions=[
                FocDemoDecision(
                    id="passive-first-liquid-ready",
                    title="被动优先并预留液冷",
                    choice="首版采用导热环、冷板和外壳散热肋，同时保留环形液冷接口。",
                    why="满足无风扇约束，并为筛选超温保留可验证的升级路径。",
                    tradeoff="液冷预留会增加密封、加工和质量控制复杂度。",
                    evidence=evidence,
                    validation="先做热网络与台架测试；超温时再执行 CFD 和液冷流阻验证。",
                    confidence="medium",
                )
            ],
            risks=[
                "当前结果是集总参数筛选，不是 CFD，不能证明局部热点安全。",
                "Rodin/Bang 仅为概念网格，不是可制造 CAD，组件语义需人工确认。",
            ],
            validation_tasks=[
                "建立电机与 MOSFET 双热源 CFD/共轭传热模型。",
                "用样机热电偶复核接触热阻、自然对流和热点温度。",
                "在制造前重建参数化 CAD 并完成公差、密封和质量审核。",
            ],
        )

    @staticmethod
    def _stages(
        data: dict[str, Any], assets: list[FocDemoAsset], mesh: FocDemoMeshStructure
    ) -> list[FocDemoStage]:
        calls = data.get("external_calls") or {}
        brief = data.get("confirmed_brief") or {}
        thermal = data.get("screening_evaluation") or {}

        def status_done(condition: bool) -> str:
            return "done" if condition else "pending"

        return [
            FocDemoStage(id="brief", label="Engineering brief", status=status_done(brief.get("state") == "confirmed")),
            FocDemoStage(id="thermal", label="Screening thermal estimate", status=status_done(bool(thermal))),
            FocDemoStage(id="reasoning", label="Model reasoning", status=status_done((calls.get("gpt_5_6_sol") or {}).get("status") == "success")),
            FocDemoStage(id="rodin", label="Rodin concept mesh", status=status_done((calls.get("hyper3d_rodin") or {}).get("status") == "done")),
            FocDemoStage(id="bang", label="Bang decomposition", status=status_done((calls.get("hyper3d_bang") or {}).get("status") == "done")),
            FocDemoStage(id="assets", label="Local asset persistence", status=status_done(bool(assets))),
            FocDemoStage(id="mesh", label="Mesh structure audit", status=status_done(mesh.mesh_count > 0)),
        ]

    @staticmethod
    def _limitations(data: dict[str, Any], thermal: FocDemoThermal) -> list[str]:
        values = [
            *list(data.get("disclaimers") or []),
            *thermal.limitations,
            "筛选结果为集总热模型，不是 CFD。",
            "Rodin/Bang 输出为概念网格，不是可制造 CAD。",
        ]
        return list(dict.fromkeys(str(value) for value in values if value))
