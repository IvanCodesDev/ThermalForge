"""概念 3D 组件清单与工程分析 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.api.routes.models import get_openai_client
from core.config import Settings, get_settings
from core.providers.errors import ProviderError
from core.providers.openai_models import OpenAIModelsClient
from core.services.component_analysis import ComponentAnalysisRequest, ComponentAnalyzer

router = APIRouter(prefix="/api/v1/components", tags=["component-analysis"])


@router.post("/analyze")
async def analyze_components(
    body: ComponentAnalysisRequest,
    client: OpenAIModelsClient = Depends(get_openai_client),
    settings: Settings = Depends(get_settings),
):
    """生成前端可消费的 ComponentManifest；AI 分析可按请求开关。"""
    if settings.is_real and not body.use_ai:
        raise HTTPException(
            status_code=422,
            detail="REAL mode requires use_ai=true; deterministic component fallback is disabled",
        )
    analyzer = ComponentAnalyzer(client if body.use_ai else None)
    try:
        return await analyzer.analyze(body)
    except ProviderError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"provider": exc.provider, "message": exc.message, "upstream": exc.details},
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
