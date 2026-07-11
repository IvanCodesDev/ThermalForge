"""OpenAI GPT-5.5 与 GPT Image 2 HTTP 客户端。"""
from __future__ import annotations

import json
from typing import Any

import httpx

from core.config import Settings
from core.providers.errors import ProviderError


class OpenAIModelsClient:
    def __init__(self, settings: Settings, transport: httpx.AsyncBaseTransport | None = None):
        self.settings = settings
        self.transport = transport

    def _headers(self) -> dict[str, str]:
        if not self.settings.openai_api_key:
            raise ProviderError("openai", "OPENAI_API_KEY 尚未配置", status_code=503)
        return {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.openai_base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.ai_request_timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(url, headers=self._headers(), json=payload)
        except httpx.TimeoutException as exc:
            raise ProviderError("openai", "OpenAI 请求超时", status_code=504) from exc
        except httpx.HTTPError as exc:
            raise ProviderError("openai", f"OpenAI 网络请求失败: {exc}") from exc

        if response.is_error:
            try:
                details: object = response.json()
            except ValueError:
                details = response.text
            status = response.status_code if 400 <= response.status_code < 500 else 502
            raise ProviderError("openai", "OpenAI 上游返回错误", status_code=status, details=details)
        return response.json()

    async def create_response(
        self,
        *,
        input_data: str | list[dict[str, Any]],
        instructions: str | None = None,
        model: str | None = None,
        previous_response_id: str | None = None,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model or self.settings.openai_text_model,
            "input": input_data,
        }
        optional = {
            "instructions": instructions,
            "previous_response_id": previous_response_id,
            "temperature": temperature,
            "max_output_tokens": max_output_tokens,
            "metadata": metadata,
        }
        payload.update({key: value for key, value in optional.items() if value is not None})
        return await self._post("responses", payload)

    @staticmethod
    def extract_json_object(response: dict[str, Any]) -> dict[str, Any]:
        """从 Responses API 的 output_text 或 output content 中提取 JSON 对象。"""
        text = response.get("output_text")
        if not isinstance(text, str):
            chunks: list[str] = []
            for output in response.get("output", []):
                if not isinstance(output, dict):
                    continue
                for content in output.get("content", []):
                    if isinstance(content, dict) and isinstance(content.get("text"), str):
                        chunks.append(content["text"])
            text = "".join(chunks)
        if not text:
            raise ProviderError("openai", "组件分析响应中没有可解析文本", status_code=502)
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            payload = json.loads(stripped)
        except json.JSONDecodeError as exc:
            raise ProviderError("openai", "组件分析响应不是有效 JSON", status_code=502, details=text) from exc
        if not isinstance(payload, dict):
            raise ProviderError("openai", "组件分析响应必须是 JSON 对象", status_code=502)
        return payload

    async def generate_image(
        self,
        *,
        prompt: str,
        model: str | None = None,
        n: int = 1,
        size: str = "1024x1024",
        quality: str = "auto",
        output_format: str = "png",
        background: str = "auto",
        moderation: str = "auto",
    ) -> dict[str, Any]:
        payload = {
            "model": model or self.settings.openai_image_model,
            "prompt": prompt,
            "n": n,
            "size": size,
            "quality": quality,
            "output_format": output_format,
            "background": background,
            "moderation": moderation,
        }
        return await self._post("images/generations", payload)
