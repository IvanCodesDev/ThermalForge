from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


def utc_now() -> datetime:
    return datetime.now(UTC)


class Base(AsyncAttrs, DeclarativeBase):
    pass
