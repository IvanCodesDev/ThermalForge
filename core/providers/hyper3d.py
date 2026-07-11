"""Hyper3D Rodin 异步任务客户端。"""
from __future__ import annotations

import json
from typing import Any

import httpx

from core.config import Settings
from core.providers.errors import ProviderError


class Hyper3DClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        if not self.settings.hyper3d_api_key:
            raise ProviderError("hyper3d", "HYPER3D_API_KEY 尚未配置", status_code=503)
        return {"Authorization": f"Bearer {self.settings.hyper3d_api_key}"}

    async def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        url = f"{self.settings.hyper3d_base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.ai_request_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.request(method, url, headers=self._headers(), **kwargs)
        except httpx.TimeoutException as exc:
            raise ProviderError("hyper3d", "Hyper3D 请求超时", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("hyper3d", f"Hyper3D 网络请求失败: {exc}") from exc

        if response.is_error:
            try:
                details: object = response.json()
            except ValueError:
                details = response.text
            status = response.status_code if 400 <= response.status_code < 500 else 502
            raise ProviderError("hyper3d", "Hyper3D 上游返回错误", status_code=status, details=details)
        return response.json()

    async def submit(
        self,
        *,
        prompt: str | None,
        images: list[tuple[str, bytes, str]],
        options: dict[str, Any],
    ) -> dict[str, Any]:
        multipart: list[tuple[str, tuple[Any, ...]]] = []
        if prompt:
            multipart.append(("prompt", (None, prompt)))
        for key, value in options.items():
            if value is None:
                continue
            field_value = json.dumps(value) if isinstance(value, (dict, list, bool)) else str(value)
            multipart.append((key, (None, field_value)))
        multipart.extend(("images", item) for item in images)
        return await self._request("POST", "rodin", files=multipart)

    async def bang(
        self,
        *,
        asset_id: str | None,
        model: tuple[str, bytes, str] | None,
        image: tuple[str, bytes, str] | None,
        prompt: str | None,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        """提交 Bang 自动分件任务。

        Bang 只负责输出多个子模型，不提供工程组件名称、真实材料或装配语义。
        """
        multipart: list[tuple[str, tuple[Any, ...]]] = []
        if asset_id:
            multipart.append(("asset_id", (None, asset_id)))
        if prompt:
            multipart.append(("prompt", (None, prompt)))
        for key, value in options.items():
            if value is None:
                continue
            field_value = json.dumps(value) if isinstance(value, (dict, list, bool)) else str(value)
            multipart.append((key, (None, field_value)))
        if model:
            multipart.append(("model", model))
        if image:
            multipart.append(("image", image))
        return await self._request("POST", "bang", files=multipart)

    async def check_status(self, *, subscription_key: str) -> dict[str, Any]:
        return await self._request(
            "POST",
            "status",
            json={"subscription_key": subscription_key},
        )

    async def check_balance(self) -> dict[str, Any]:
        return await self._request("GET", "check_balance")

    async def download(self, *, task_uuid: str) -> dict[str, Any]:
        return await self._request("POST", "download", json={"task_uuid": task_uuid})
