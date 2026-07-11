"""Hyper3D、GPT Image 2 与兼容 Responses API 路由。"""
from __future__ import annotations

import base64
import binascii

from fastapi import APIRouter, Depends, HTTPException

from core.api.schemas_ai import (
    GPT55ResponseIn,
    GPTImage2GenerateIn,
    Hyper3DBangIn,
    Hyper3DDownloadIn,
    Hyper3DStatusIn,
    Hyper3DSubmitIn,
)
from core.config import Settings, get_settings
from core.providers.errors import ProviderError
from core.providers.hyper3d import Hyper3DClient
from core.providers.openai_models import OpenAIModelsClient

router = APIRouter(prefix="/models", tags=["external-models"])


def get_openai_client(settings: Settings = Depends(get_settings)) -> OpenAIModelsClient:
    return OpenAIModelsClient(settings)


def get_hyper3d_client(settings: Settings = Depends(get_settings)) -> Hyper3DClient:
    return Hyper3DClient(settings)


def _raise_provider_error(exc: ProviderError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail={
            "provider": exc.provider,
            "message": exc.message,
            "upstream": exc.details,
        },
    ) from exc


@router.get("/config")
async def model_config(settings: Settings = Depends(get_settings)):
    """返回可公开的模型配置，不回显任何密钥。"""
    return {
        "openai": {
            "configured": bool(settings.openai_api_key),
            "text_model": settings.openai_text_model,
            "image_model": settings.openai_image_model,
        },
        "hyper3d": {"configured": bool(settings.hyper3d_api_key)},
        "timeout_seconds": settings.ai_request_timeout_seconds,
        "routes": {
            "text_responses": "/models/text/responses",
            "gpt_5_5": "/models/gpt-5.5/responses",
            "gpt_image_2": "/models/gpt-image-2/generations",
            "hyper3d_submit": "/models/hyper3d/tasks",
            "hyper3d_bang": "/models/hyper3d/bang",
            "hyper3d_balance": "/models/hyper3d/balance",
            "hyper3d_status": "/models/hyper3d/status",
            "hyper3d_download": "/models/hyper3d/download",
        },
    }


@router.post("/text/responses")
@router.post("/gpt-5.5/responses")
async def text_responses(
    body: GPT55ResponseIn,
    client: OpenAIModelsClient = Depends(get_openai_client),
):
    """代理 OpenAI Responses API，默认模型由 OPENAI_TEXT_MODEL 管理。"""
    try:
        return await client.create_response(
            input_data=body.input,
            instructions=body.instructions,
            model=body.model,
            previous_response_id=body.previous_response_id,
            temperature=body.temperature,
            max_output_tokens=body.max_output_tokens,
            metadata=body.metadata,
        )
    except ProviderError as exc:
        _raise_provider_error(exc)


@router.post("/gpt-image-2/generations")
async def gpt_image_2_generations(
    body: GPTImage2GenerateIn,
    client: OpenAIModelsClient = Depends(get_openai_client),
):
    """代理 OpenAI Image API，默认模型为 gpt-image-2。"""
    try:
        return await client.generate_image(
            prompt=body.prompt,
            model=body.model,
            n=body.n,
            size=body.size,
            quality=body.quality,
            output_format=body.output_format,
            background=body.background,
            moderation=body.moderation,
        )
    except ProviderError as exc:
        _raise_provider_error(exc)


@router.post("/hyper3d/tasks")
async def hyper3d_submit(
    body: Hyper3DSubmitIn,
    client: Hyper3DClient = Depends(get_hyper3d_client),
):
    """提交 Hyper3D Rodin 文生或图生 3D 异步任务。"""
    decoded_images: list[tuple[str, bytes, str]] = []
    for image in body.images:
        try:
            content = base64.b64decode(image.content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise HTTPException(422, f"图片 {image.filename} 不是有效 Base64") from exc
        decoded_images.append((image.filename, content, image.content_type))

    try:
        return await client.submit(
            prompt=body.prompt,
            images=decoded_images,
            options=body.options.model_dump(by_alias=True, exclude_none=True),
        )
    except ProviderError as exc:
        _raise_provider_error(exc)


@router.post("/hyper3d/bang")
async def hyper3d_bang(
    body: Hyper3DBangIn,
    client: Hyper3DClient = Depends(get_hyper3d_client),
):
    """提交 Bang 分件任务，支持 Rodin asset_id 或自定义模型上传。"""
    decoded_model: tuple[str, bytes, str] | None = None
    decoded_image: tuple[str, bytes, str] | None = None
    try:
        if body.model:
            decoded_model = (
                body.model.filename,
                base64.b64decode(body.model.content_base64, validate=True),
                body.model.content_type,
            )
        if body.image:
            decoded_image = (
                body.image.filename,
                base64.b64decode(body.image.content_base64, validate=True),
                body.image.content_type,
            )
    except (binascii.Error, ValueError) as exc:
        raise HTTPException(422, "Bang 输入文件不是有效 Base64") from exc

    try:
        return await client.bang(
            asset_id=body.asset_id,
            model=decoded_model,
            image=decoded_image,
            prompt=body.prompt,
            options={
                "strength": body.strength,
                "geometry_file_format": body.geometry_file_format,
                "material": body.material,
                "resolution": body.resolution,
            },
        )
    except ProviderError as exc:
        _raise_provider_error(exc)


@router.get("/hyper3d/balance")
async def hyper3d_balance(
    client: Hyper3DClient = Depends(get_hyper3d_client),
):
    """查询 Hyper3D 余额，不提交生成任务。"""
    try:
        return await client.check_balance()
    except ProviderError as exc:
        _raise_provider_error(exc)


@router.post("/hyper3d/status")
async def hyper3d_status(
    body: Hyper3DStatusIn,
    client: Hyper3DClient = Depends(get_hyper3d_client),
):
    """按提交响应中的 subscription_key 查询任务进度。"""
    try:
        return await client.check_status(subscription_key=body.subscription_key)
    except ProviderError as exc:
        _raise_provider_error(exc)


@router.post("/hyper3d/download")
async def hyper3d_download(
    body: Hyper3DDownloadIn,
    client: Hyper3DClient = Depends(get_hyper3d_client),
):
    """任务完成后按 task_uuid 获取模型下载列表。"""
    try:
        return await client.download(task_uuid=body.task_uuid)
    except ProviderError as exc:
        _raise_provider_error(exc)
