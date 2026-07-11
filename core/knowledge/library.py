"""全局共享知识库（特性二）。

零依赖实现：仅使用 Python 标准库 ``sqlite3``。单库 ``data/knowledge.db``，
含 ``motors`` / ``materials`` / ``docs`` 三张表，分别在 ``motor_type`` /
``material`` / ``keyword`` 列上建立索引（OQ2）。所有 ``upsert_*`` 以
``content_hash``（源内容 SHA-256）实现幂等（OQ7 / 知识库可重复种子）。
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from core.config import PROJECT_ROOT

DATA_DIR = PROJECT_ROOT / "data"


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MotorEntry(_StrictModel):
    entry_id: str = Field(min_length=1)
    motor_type: str
    params_json: str
    source_id: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class MaterialEntry(_StrictModel):
    material_id: str = Field(min_length=1)
    name: str
    properties_json: str
    source_id: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")


class DocEntry(_StrictModel):
    doc_id: str = Field(min_length=1)
    filename: str
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: str
    extracted_json: str
    keyword: str = ""


def sha256_hex(data: bytes | str) -> str:
    """返回数据（字节或字符串）的 SHA-256 十六进制摘要。"""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def _entry_id(prefix: str, content_hash: str) -> str:
    return f"{prefix}-{content_hash[:16]}"


class KnowledgeLibrary:
    """sqlite3 封装的知识库；全局共享、幂等 upsert、三类检索。"""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = Path(db_path) if db_path is not None else (DATA_DIR / "knowledge.db")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS motors ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "motor_type TEXT NOT NULL, "
                "params_json TEXT NOT NULL, "
                "source_id TEXT NOT NULL, "
                "content_hash TEXT NOT NULL UNIQUE)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_motors_motor_type ON motors(motor_type)")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS materials ("
                "material_id TEXT PRIMARY KEY, "
                "name TEXT NOT NULL, "
                "properties_json TEXT NOT NULL, "
                "source_id TEXT NOT NULL, "
                "content_hash TEXT NOT NULL)"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_materials_material ON materials(material_id)")
            conn.execute(
                "CREATE TABLE IF NOT EXISTS docs ("
                "doc_id TEXT PRIMARY KEY, "
                "filename TEXT NOT NULL, "
                "content_hash TEXT NOT NULL UNIQUE, "
                "status TEXT NOT NULL, "
                "extracted_json TEXT NOT NULL, "
                "keyword TEXT NOT NULL DEFAULT '')"
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_docs_keyword ON docs(keyword)")

    # ----- upsert（content_hash 幂等）-----

    def upsert_motor(self, entry: MotorEntry) -> MotorEntry:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO motors (motor_type, params_json, source_id, content_hash) "
                "VALUES (?, ?, ?, ?)",
                (entry.motor_type, entry.params_json, entry.source_id, entry.content_hash),
            )
            row = conn.execute(
                "SELECT motor_type, params_json, source_id, content_hash FROM motors WHERE content_hash=?",
                (entry.content_hash,),
            ).fetchone()
        return MotorEntry(
            entry_id=_entry_id("kb-motor", row[3]),
            motor_type=row[0],
            params_json=row[1],
            source_id=row[2],
            content_hash=row[3],
        )

    def upsert_material(self, entry: MaterialEntry) -> MaterialEntry:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO materials "
                "(material_id, name, properties_json, source_id, content_hash) VALUES (?, ?, ?, ?, ?)",
                (entry.material_id, entry.name, entry.properties_json, entry.source_id, entry.content_hash),
            )
            row = conn.execute(
                "SELECT material_id, name, properties_json, source_id, content_hash "
                "FROM materials WHERE material_id=?",
                (entry.material_id,),
            ).fetchone()
        return MaterialEntry(
            material_id=row[0],
            name=row[1],
            properties_json=row[2],
            source_id=row[3],
            content_hash=row[4],
        )

    def upsert_doc(self, entry: DocEntry) -> DocEntry:
        with self._connect() as conn:
            conn.execute(
                "INSERT OR IGNORE INTO docs "
                "(doc_id, filename, content_hash, status, extracted_json, keyword) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (entry.doc_id, entry.filename, entry.content_hash, entry.status, entry.extracted_json, entry.keyword),
            )
            row = conn.execute(
                "SELECT doc_id, filename, content_hash, status, extracted_json, keyword "
                "FROM docs WHERE content_hash=?",
                (entry.content_hash,),
            ).fetchone()
        return DocEntry(
            doc_id=row[0],
            filename=row[1],
            content_hash=row[2],
            status=row[3],
            extracted_json=row[4],
            keyword=row[5],
        )

    # ----- 检索 -----

    def search_by_motor_type(self, motor_type: str) -> list[MotorEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT motor_type, params_json, source_id, content_hash FROM motors WHERE motor_type=?",
                (motor_type,),
            ).fetchall()
        return [
            MotorEntry(
                entry_id=_entry_id("kb-motor", r[3]),
                motor_type=r[0],
                params_json=r[1],
                source_id=r[2],
                content_hash=r[3],
            )
            for r in rows
        ]

    def search_by_material(self, name: str) -> list[MaterialEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT material_id, name, properties_json, source_id, content_hash "
                "FROM materials WHERE material_id=? OR name LIKE ?",
                (name, f"%{name}%"),
            ).fetchall()
        return [
            MaterialEntry(
                material_id=r[0],
                name=r[1],
                properties_json=r[2],
                source_id=r[3],
                content_hash=r[4],
            )
            for r in rows
        ]

    def search_by_keyword(self, text: str) -> list[DocEntry]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT doc_id, filename, content_hash, status, extracted_json, keyword "
                "FROM docs WHERE keyword LIKE ? OR filename LIKE ?",
                (f"%{text}%", f"%{text}%"),
            ).fetchall()
        return [
            DocEntry(
                doc_id=r[0],
                filename=r[1],
                content_hash=r[2],
                status=r[3],
                extracted_json=r[4],
                keyword=r[5],
            )
            for r in rows
        ]
