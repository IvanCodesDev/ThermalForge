"""Versioned SQLite JSON storage for governed backend state."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any


class DocumentNotFoundError(LookupError):
    pass


class DocumentConflictError(ValueError):
    pass


class SQLiteDocumentStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS documents ("
                "namespace TEXT NOT NULL, document_key TEXT NOT NULL, "
                "revision INTEGER NOT NULL CHECK(revision >= 1), payload TEXT NOT NULL, "
                "created_at TEXT NOT NULL, PRIMARY KEY(namespace, document_key, revision))"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS idx_documents_latest "
                "ON documents(namespace, document_key, revision DESC)"
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=30)
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    def put(self, namespace: str, key: str, revision: int, payload: dict[str, Any]) -> None:
        if not namespace or not key or revision < 1:
            raise ValueError("namespace, key and positive revision are required")
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self._connect() as connection:
            try:
                connection.execute(
                    "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
                    (namespace, key, revision, serialized, datetime.now(timezone.utc).isoformat()),
                )
            except sqlite3.IntegrityError as exc:
                raise DocumentConflictError(f"{namespace}/{key} revision {revision} exists") from exc

    def put_next(self, namespace: str, key: str, payload: dict[str, Any]) -> int:
        """Atomically append an audit snapshot and return its storage revision."""
        if not namespace or not key:
            raise ValueError("namespace and key are required")
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT COALESCE(MAX(revision), 0) FROM documents WHERE namespace=? AND document_key=?",
                (namespace, key),
            ).fetchone()
            revision = int(row[0]) + 1
            connection.execute(
                "INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
                (namespace, key, revision, serialized, datetime.now(timezone.utc).isoformat()),
            )
        return revision

    def get(self, namespace: str, key: str, revision: int | None = None) -> dict[str, Any]:
        query = "SELECT payload FROM documents WHERE namespace=? AND document_key=?"
        parameters: list[Any] = [namespace, key]
        if revision is None:
            query += " ORDER BY revision DESC LIMIT 1"
        else:
            query += " AND revision=?"
            parameters.append(revision)
        with self._lock, self._connect() as connection:
            row = connection.execute(query, parameters).fetchone()
        if row is None:
            raise DocumentNotFoundError(f"{namespace}/{key}/{revision or 'latest'} not found")
        value = json.loads(row[0])
        if not isinstance(value, dict):
            raise ValueError("stored payload is not an object")
        return value

    def list_latest(self, namespace: str) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT d.payload FROM documents d JOIN ("
                "SELECT document_key, MAX(revision) revision FROM documents "
                "WHERE namespace=? GROUP BY document_key) latest "
                "ON d.document_key=latest.document_key AND d.revision=latest.revision "
                "WHERE d.namespace=? ORDER BY d.document_key",
                (namespace, namespace),
            ).fetchall()
        return [json.loads(row[0]) for row in rows]
