"""Safe API routes for the reproducible FOC arm thermal demo."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import ValidationError

from core.api.routes.models import get_openai_client
from core.models.foc_demo import FocDemoDesign, FocDemoSnapshot
from core.providers.errors import ProviderError
from core.providers.openai_models import OpenAIModelsClient
from core.services.foc_demo import AssetNotFoundError, FocDemoRepository


router = APIRouter(prefix="/api/v1/foc-demo", tags=["foc-demo"])

_MEDIA_TYPES = {
    ".glb": "model/gltf-binary",
    ".webp": "image/webp",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

_REASONING_INSTRUCTIONS = """
Return one JSON object describing an auditable FOC joint thermal design ledger.
Required fields are architecture, heat_paths, decisions, risks, and
validation_tasks. Base claims only on the supplied engineering context. Keep
screening estimates distinct from CFD or manufacturing validation. Provide
concise evidence and tradeoffs, not hidden chain-of-thought.
""".strip()


def get_foc_demo_repository() -> FocDemoRepository:
    return FocDemoRepository()


def _raise_provider_error(exc: ProviderError) -> None:
    status_code = exc.status_code if 400 <= exc.status_code <= 599 else 502
    provider = "openai" if exc.provider.strip().lower() == "openai" else "model_provider"
    raise HTTPException(
        status_code=status_code,
        detail={
            "provider": provider,
            "message": "Unable to refresh FOC design reasoning",
        },
    ) from exc


@router.get("", response_model=FocDemoSnapshot)
def foc_demo_snapshot(
    repository: FocDemoRepository = Depends(get_foc_demo_repository),
) -> FocDemoSnapshot:
    return repository.snapshot()


@router.get("/raw")
def foc_demo_raw(
    repository: FocDemoRepository = Depends(get_foc_demo_repository),
) -> dict[str, object]:
    return repository.raw()


@router.get("/assets/{name:path}")
def foc_demo_asset(
    name: str,
    repository: FocDemoRepository = Depends(get_foc_demo_repository),
) -> FileResponse:
    try:
        path = repository.resolve_asset(name)
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail="FOC demo asset not found") from exc

    media_type = _MEDIA_TYPES.get(Path(name).suffix.lower())
    if media_type is None:
        raise HTTPException(status_code=404, detail="FOC demo asset not found")
    return FileResponse(path=path, media_type=media_type)


@router.post("/reasoning", response_model=FocDemoDesign)
async def refresh_foc_demo_reasoning(
    repository: FocDemoRepository = Depends(get_foc_demo_repository),
    client: OpenAIModelsClient = Depends(get_openai_client),
) -> FocDemoDesign:
    snapshot = repository.snapshot()
    reasoning_context = {
        "scenario": snapshot.scenario,
        "engineering_input": snapshot.engineering_input,
        "brief": snapshot.brief,
        "thermal": snapshot.thermal.model_dump(mode="json"),
        "foc_simulation": snapshot.foc_simulation,
        "limitations": snapshot.limitations,
    }

    try:
        response = await client.create_response(
            input_data=json.dumps(reasoning_context, ensure_ascii=False),
            instructions=_REASONING_INSTRUCTIONS,
            metadata={"workflow": "thermalforge_foc_demo_reasoning"},
        )
        payload = OpenAIModelsClient.extract_json_object(response)
        return repository.persist_design(payload)
    except ProviderError as exc:
        _raise_provider_error(exc)
    except ValidationError as exc:
        raise HTTPException(
            status_code=502,
            detail="Model returned an invalid FOC design ledger",
        ) from exc
