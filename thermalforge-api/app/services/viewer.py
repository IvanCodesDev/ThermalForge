from dataclasses import dataclass
from functools import lru_cache
from hashlib import file_digest
from pathlib import Path, PurePosixPath
from typing import cast

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings
from app.domain.enums import ArtifactKind, QualityStatus
from app.domain.errors import UnsupportedViewerModelFormat, ViewerModelNotFound
from app.models import ArtifactModel
from app.repositories.artifacts import ArtifactRepository
from app.services.tasks import TaskService
from app.viewer.schemas import (
    ViewerAsset,
    ViewerLibrary,
    ViewerLibraryModel,
    ViewerManifest,
    ViewerModelFormat,
    ViewerModelKind,
    ViewerPart,
    ViewerTransform,
    ViewerVariant,
)

_MODEL_KINDS = (ArtifactKind.NORMALIZED_MODEL, ArtifactKind.RAW_MODEL)
_FORMATS = {"stl", "glb", "gltf", "obj"}
_MIME_FORMATS: dict[str, ViewerModelFormat] = {
    "application/sla": "stl",
    "application/vnd.ms-pki.stl": "stl",
    "model/stl": "stl",
    "model/gltf-binary": "glb",
    "model/gltf+json": "gltf",
    "model/obj": "obj",
}
_SEGMENT_NODE_NAMES = ("root.0", "root.1", "root.2")
_CONCEPT_NOTICE = (
    "该资产是用于界面演示与方案沟通的概念网格，不是动态生成的可制造 CAD。"
)


@dataclass(frozen=True, slots=True)
class _LibrarySpec:
    id: str
    label: str
    description: str
    filename_setting: str
    kind: ViewerModelKind
    node_names: tuple[str, ...] = ()


_LIBRARY_SPECS = (
    _LibrarySpec(
        id="foc-segmented",
        label="FOC 机械臂 · 分件参考",
        description="Bang 分件概念网格，可验证节点选择、线框与爆炸交互。",
        filename_setting="segmented_model_filename",
        kind="normalized_model",
        node_names=_SEGMENT_NODE_NAMES,
    ),
    _LibrarySpec(
        id="foc-whole",
        label="FOC 机械臂 · 整体参考",
        description="用于观察整体比例、外形与热结构语言的 FOC 机械臂概念网格。",
        filename_setting="whole_model_filename",
        kind="raw_model",
    ),
    _LibrarySpec(
        id="hyper3d-original",
        label="Hyper3D 机械臂 · 原始概念",
        description="Hyper3D 返回的原始概念网格，用于与后续分件结果对照。",
        filename_setting="hyper3d_model_filename",
        kind="raw_model",
    ),
)


@lru_cache(maxsize=32)
def _sha256(path: str, modified_ns: int, size_bytes: int) -> str:
    del modified_ns, size_bytes
    with Path(path).open("rb") as source:
        return file_digest(source, "sha256").hexdigest()


def _parts_for_nodes(
    variant_id: str,
    variant_label: str,
    node_names: list[str],
) -> list[ViewerPart]:
    if not node_names:
        return [
            ViewerPart(
                id=f"{variant_id}-whole",
                label=variant_label,
                description="当前资产未提供可验证的分件节点。",
                binding="whole_asset",
            )
        ]

    offsets = (
        (0.55, 0.0, 0.0),
        (-0.55, 0.0, 0.0),
        (0.0, 0.55, 0.0),
        (0.0, -0.55, 0.0),
        (0.0, 0.0, 0.55),
        (0.0, 0.0, -0.55),
    )
    return [
        ViewerPart(
            id=f"{variant_id}-part-{index + 1}",
            label=f"分件网格 {index + 1:02d}",
            description=f"模型节点 {node_name}；尚未建立可验证的工程语义映射。",
            binding="node_names",
            node_names=[node_name],
            explode=offsets[index % len(offsets)],
        )
        for index, node_name in enumerate(node_names)
    ]


class ViewerLibraryService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get_library(self) -> ViewerLibrary:
        models = [
            model
            for spec in _LIBRARY_SPECS
            if (model := self._to_model(spec)) is not None
        ]
        return ViewerLibrary(models=models)

    def get_model_path(self, model_id: str) -> tuple[Path, ViewerAsset]:
        spec = next(
            (candidate for candidate in _LIBRARY_SPECS if candidate.id == model_id),
            None,
        )
        model = self._to_model(spec) if spec is not None else None
        if spec is None or model is None:
            raise ViewerModelNotFound(model_id)
        return self._resolve_path(spec), model.asset

    def _to_model(self, spec: _LibrarySpec) -> ViewerLibraryModel | None:
        try:
            path = self._resolve_path(spec)
        except ViewerModelNotFound:
            return None
        stat = path.stat()
        parts = _parts_for_nodes(spec.id, spec.label, list(spec.node_names))
        asset = ViewerAsset(
            artifact_id=spec.id,
            kind=spec.kind,
            url=f"/v1/viewer-library/{spec.id}/content",
            format="glb",
            mime_type="model/gltf-binary",
            sha256=_sha256(str(path), stat.st_mtime_ns, stat.st_size),
            size_bytes=stat.st_size,
        )
        return ViewerLibraryModel(
            id=spec.id,
            label=spec.label,
            description=spec.description,
            asset=asset,
            supports_explosion=any(part.explode is not None for part in parts),
            parts=parts,
            notices=[_CONCEPT_NOTICE],
        )

    def _resolve_path(self, spec: _LibrarySpec) -> Path:
        root = self._settings.model_asset_root.resolve()
        filename = cast(str, getattr(self._settings, spec.filename_setting))
        candidate = (root / filename).resolve()
        if (
            not candidate.is_relative_to(root)
            or candidate.suffix.lower() != ".glb"
            or not candidate.is_file()
        ):
            raise ViewerModelNotFound(spec.id)
        return candidate


class ViewerService:
    def __init__(self, session: AsyncSession) -> None:
        self._artifacts = ArtifactRepository(session)
        self._tasks = TaskService(session)

    async def get_manifest(self, task_id: str) -> ViewerManifest:
        await self._tasks.get_task(task_id)
        artifacts = await self._get_approved_models(task_id)
        variants: list[ViewerVariant] = []
        unsupported = False
        for artifact in artifacts:
            try:
                variants.append(self._to_variant(task_id, artifact))
            except UnsupportedViewerModelFormat:
                unsupported = True

        if not variants:
            if unsupported:
                raise UnsupportedViewerModelFormat()
            raise ViewerModelNotFound(task_id)

        notices = (
            [
                "当前模型是与任务热设计关联的概念参考模型，不是按本次输入动态生成的可制造 CAD。"
            ]
            if any(
                artifact.metadata_json.get("source") == "curated_reference"
                for artifact in artifacts
            )
            else []
        )
        return ViewerManifest(
            task_id=task_id,
            asset=variants[0].asset,
            variants=variants,
            notices=notices,
        )

    async def get_downloadable_model(
        self,
        *,
        task_id: str,
        artifact_id: str,
    ) -> ArtifactModel:
        await self._tasks.get_task(task_id)
        artifact = await self._artifacts.get_for_task(
            task_id=task_id,
            artifact_id=artifact_id,
        )
        if (
            artifact is None
            or artifact.kind not in {kind.value for kind in _MODEL_KINDS}
            or artifact.quality_status != QualityStatus.APPROVED.value
        ):
            raise ViewerModelNotFound(task_id)
        return artifact

    async def _get_approved_models(self, task_id: str) -> list[ArtifactModel]:
        artifacts: list[ArtifactModel] = []
        for kind in _MODEL_KINDS:
            artifact = await self._artifacts.get_latest_approved(
                task_id=task_id,
                kind=kind,
            )
            if artifact is not None:
                artifacts.append(artifact)
        return artifacts

    def _to_variant(
        self,
        task_id: str,
        artifact: ArtifactModel,
    ) -> ViewerVariant:
        asset = ViewerAsset(
            artifact_id=artifact.id,
            kind=cast(ViewerModelKind, artifact.kind),
            url=f"/v1/tasks/{task_id}/models/{artifact.id}/content",
            format=self._resolve_format(artifact),
            mime_type=artifact.mime_type,
            sha256=artifact.sha256,
            size_bytes=artifact.size_bytes,
            transform=self._resolve_transform(artifact),
        )
        variant_id = self._variant_id(artifact)
        label = self._variant_label(variant_id, artifact.kind)
        parts = self._parts(artifact, variant_id, label)
        return ViewerVariant(
            id=variant_id,
            label=label,
            asset=asset,
            supports_explosion=any(part.explode is not None for part in parts),
            parts=parts,
        )

    @staticmethod
    def _variant_id(artifact: ArtifactModel) -> str:
        value = artifact.metadata_json.get("variant")
        if isinstance(value, str) and value.strip():
            return value.strip()[:80]
        return artifact.kind

    @staticmethod
    def _variant_label(variant_id: str, kind: str) -> str:
        if variant_id == "segmented":
            return "分件参考模型"
        if variant_id == "whole":
            return "整体参考模型"
        if kind == ArtifactKind.NORMALIZED_MODEL.value:
            return "标准化模型"
        return "原始模型"

    @staticmethod
    def _parts(
        artifact: ArtifactModel,
        variant_id: str,
        variant_label: str,
    ) -> list[ViewerPart]:
        raw_node_names = artifact.metadata_json.get("node_names")
        node_names = (
            list(
                dict.fromkeys(
                    name.strip()
                    for name in raw_node_names
                    if isinstance(name, str) and name.strip()
                )
            )[:100]
            if isinstance(raw_node_names, list)
            else []
        )
        return _parts_for_nodes(variant_id, variant_label, node_names)

    @staticmethod
    def _resolve_format(artifact: ArtifactModel) -> ViewerModelFormat:
        metadata_format = artifact.metadata_json.get("format")
        if isinstance(metadata_format, str):
            normalized_format = metadata_format.lower().lstrip(".")
            if normalized_format in _FORMATS:
                return cast(ViewerModelFormat, normalized_format)

        filename = artifact.metadata_json.get("filename")
        format_sources = [filename, artifact.storage_uri]
        for source in format_sources:
            if not isinstance(source, str):
                continue
            extension = PurePosixPath(source.replace("\\", "/")).suffix.lower().lstrip(".")
            if extension in _FORMATS:
                return cast(ViewerModelFormat, extension)

        mime_type = artifact.mime_type.partition(";")[0].strip().lower()
        model_format = _MIME_FORMATS.get(mime_type)
        if model_format is None:
            raise UnsupportedViewerModelFormat()
        return model_format

    @staticmethod
    def _resolve_transform(artifact: ArtifactModel) -> ViewerTransform:
        metadata_transform = artifact.metadata_json.get("transform")
        if not isinstance(metadata_transform, dict):
            return ViewerTransform()
        try:
            return ViewerTransform.model_validate(metadata_transform)
        except ValidationError:
            return ViewerTransform()
