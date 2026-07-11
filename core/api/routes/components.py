"""概念 3D 组件清单与工程分析 API。"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from core.api.routes.models import get_openai_client
from core.config import Settings, get_settings
from core.providers.errors import ProviderError
from core.providers.openai_models import OpenAIModelsClient
from core.services.component_analysis import ComponentAnalysisRequest, ComponentAnalyzer

router = APIRouter(prefix="/api/v1/components", tags=["component-analysis"])


@router.post("/analyze",
             summary="组件工程分析",
             description="对概念 3D 组件清单做工程分析，输出前端可消费的 ComponentManifest。AI 分析可由请求体 use_ai 开关；"
             "REAL 模式下强制 use_ai=true（关闭确定性回退）。",
             response_description="ComponentManifest",
             responses={200: {"description": "分析成功", "content": {"application/json": {"example": {"components": [{"id": "root.0", "role": "shell", "material": "PA12-CF"}]}}}}, 422: {"description": "REAL 模式要求 use_ai=true 或参数校验失败"}, 502: {"description": "上游模型服务错误"}})
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
