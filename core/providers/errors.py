"""第三方服务统一异常。"""
from __future__ import annotations


class ProviderError(RuntimeError):
    def __init__(self, provider: str, message: str, *, status_code: int = 502, details: object = None):
        super().__init__(message)
        self.provider = provider
        self.message = message
        self.status_code = status_code
        self.details = details
