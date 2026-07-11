from __future__ import annotations

from fastapi.testclient import TestClient

from core.api.app import app
from core.models.components import ComponentAsset
from core.services.component_analysis import (
    ComponentAnalysisRequest,
    ComponentAnalyzer,
    normalize_hyper3d_download,
)


def test_normalize_hyper3d_download():
    assets = normalize_hyper3d_download(
        {"list": [{"url": "https://asset.test/part-1.glb", "name": "part-1.glb"}]}
    )
    assert assets[0].filename == "part-1.glb"
    assert assets[0].format == "glb"


def test_deterministic_component_manifest_keeps_uncertainty_explicit():
    request = ComponentAnalysisRequest(
        decomposition_task_uuid="bang-1",
        files=[ComponentAsset(url="https://asset.test/part.glb", filename="part.glb", format="glb")],
    )
    manifest = __import__("asyncio").run(ComponentAnalyzer().analyze(request))
    component = manifest.components[0]
    assert component.semantic_type == "unknown"
    assert component.requires_material_confirmation is True
    assert manifest.fidelity == "concept_mesh"
    assert "AI 候选" in manifest.material_disclaimer


def test_component_analysis_api_without_paid_ai_call():
    client = TestClient(app)
    response = client.post(
        "/api/v1/components/analyze",
        json={
            "decomposition_task_uuid": "bang-1",
            "strength": 6,
            "files": [
                {
                    "url": "https://asset.test/part.glb",
                    "filename": "part.glb",
                    "format": "glb",
                }
            ],
            "use_ai": False,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["decomposition_provider"] == "hyper3d_bang"
    assert payload["components"][0]["review_status"] == "needs_review"
