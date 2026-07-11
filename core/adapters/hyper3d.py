"""Hyper3D 展示资产归一化边界。"""
from core.models.engineering_state import Artifact, ArtifactFidelity

class Hyper3DAdapter:
    """将提供方返回资产永久登记为概念网格。"""
    def normalize_artifact(self, artifact: Artifact) -> Artifact:
        return artifact.model_copy(update={"provider": "hyper3d", "fidelity": ArtifactFidelity.CONCEPT_MESH})
