from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat

ViewerModelFormat = Literal["stl", "glb", "gltf", "obj"]
ViewerModelKind = Literal["raw_model", "normalized_model"]
ViewerPartBinding = Literal["whole_asset", "node_names"]


class ViewerTransform(BaseModel):
    model_config = ConfigDict(extra="ignore")

    translation: tuple[FiniteFloat, FiniteFloat, FiniteFloat] = (0.0, 0.0, 0.0)
    rotation: tuple[FiniteFloat, FiniteFloat, FiniteFloat, FiniteFloat] = Field(
        default=(0.0, 0.0, 0.0, 1.0),
        description="Rotation quaternion ordered as x, y, z, w.",
    )
    scale: tuple[FiniteFloat, FiniteFloat, FiniteFloat] = (1.0, 1.0, 1.0)


class ViewerAsset(BaseModel):
    artifact_id: str
    kind: ViewerModelKind
    url: str
    format: ViewerModelFormat
    mime_type: str
    sha256: str
    size_bytes: int
    transform: ViewerTransform = Field(default_factory=ViewerTransform)


class ViewerPart(BaseModel):
    id: str
    label: str
    description: str
    binding: ViewerPartBinding
    node_names: list[str] = Field(default_factory=list)
    explode: tuple[FiniteFloat, FiniteFloat, FiniteFloat] | None = None


class ViewerVariant(BaseModel):
    id: str
    label: str
    asset: ViewerAsset
    supports_explosion: bool = False
    parts: list[ViewerPart] = Field(default_factory=list)


class ViewerManifest(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    task_id: str
    asset: ViewerAsset
    variants: list[ViewerVariant] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class ViewerLibraryModel(BaseModel):
    id: str
    label: str
    description: str
    asset: ViewerAsset
    supports_explosion: bool = False
    parts: list[ViewerPart] = Field(default_factory=list)
    notices: list[str] = Field(default_factory=list)


class ViewerLibrary(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    models: list[ViewerLibraryModel] = Field(default_factory=list)
