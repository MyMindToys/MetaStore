"""Local SQLite cache for incremental scans and sync queue (stdlib sqlite3 only)."""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator


SCHEMA = """
CREATE TABLE IF NOT EXISTS scanned_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    kind TEXT NOT NULL,
    size_bytes INTEGER,
    mtime_ns INTEGER,
    checksum_sha256 TEXT,
    UNIQUE(root_path, relative_path)
);

CREATE TABLE IF NOT EXISTS scanned_folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root_path TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    file_count INTEGER,
    total_size_bytes INTEGER,
    mtime_ns INTEGER,
    UNIQUE(root_path, relative_path)
);

CREATE TABLE IF NOT EXISTS sync_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payload TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    retries INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    last_error TEXT
);

CREATE TABLE IF NOT EXISTS scanner_state (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_scanned_files_root ON scanned_files(root_path);
CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status);
"""


@dataclass(slots=True)
class CachedFileRow:
    root_path: str
    relative_path: str
    kind: str
    size_bytes: int | None
    mtime_ns: int | None
    checksum_sha256: str | None


class ScannerCache:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=60)
        conn.row_factory = sqlite3.Row
        return conn

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def get_cached_file(self, root_path: str, relative_path: str) -> CachedFileRow | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT root_path, relative_path, kind, size_bytes, mtime_ns, checksum_sha256
                FROM scanned_files WHERE root_path = ? AND relative_path = ?
                """,
                (root_path, relative_path),
            ).fetchone()
        if row is None:
            return None
        return CachedFileRow(
            root_path=row["root_path"],
            relative_path=row["relative_path"],
            kind=row["kind"],
            size_bytes=row["size_bytes"],
            mtime_ns=row["mtime_ns"],
            checksum_sha256=row["checksum_sha256"],
        )

    def upsert_file(
        self,
        root_path: str,
        relative_path: str,
        kind: str,
        size_bytes: int | None,
        mtime_ns: int | None,
        checksum_sha256: str | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scanned_files (root_path, relative_path, kind, size_bytes, mtime_ns, checksum_sha256)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(root_path, relative_path) DO UPDATE SET
                    kind=excluded.kind,
                    size_bytes=excluded.size_bytes,
                    mtime_ns=excluded.mtime_ns,
                    checksum_sha256=excluded.checksum_sha256
                """,
                (root_path, relative_path, kind, size_bytes, mtime_ns, checksum_sha256),
            )

    def upsert_folder(
        self,
        root_path: str,
        relative_path: str,
        file_count: int,
        total_size_bytes: int,
        mtime_ns: int | None,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scanned_folders (root_path, relative_path, file_count, total_size_bytes, mtime_ns)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(root_path, relative_path) DO UPDATE SET
                    file_count=excluded.file_count,
                    total_size_bytes=excluded.total_size_bytes,
                    mtime_ns=excluded.mtime_ns
                """,
                (root_path, relative_path, file_count, total_size_bytes, mtime_ns),
            )

    def list_cached_paths_for_root(self, root_path: str) -> set[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT relative_path FROM scanned_files WHERE root_path = ?
                UNION
                SELECT relative_path FROM scanned_folders WHERE root_path = ?
                """,
                (root_path, root_path),
            ).fetchall()
        return {r[0] for r in rows}

    def list_cached_file_paths_for_root(self, root_path: str) -> set[str]:
        """Только файлы из кэша (не каталоги)."""
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT relative_path FROM scanned_files
                WHERE root_path = ? AND kind = 'file'
                """,
                (root_path,),
            ).fetchall()
        return {r[0] for r in rows}

    def get_cached_folder_stats(self, root_path: str, relative_path: str) -> tuple[int, int] | None:
        """Возвращает (file_count, total_size_bytes) из последнего скана или None."""
        key = relative_path if relative_path not in ("", ".") else "."
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT file_count, total_size_bytes FROM scanned_folders
                WHERE root_path = ? AND relative_path = ?
                """,
                (root_path, key),
            ).fetchone()
        if row is None:
            return None
        return (int(row[0] or 0), int(row[1] or 0))

    def delete_path_entry(self, root_path: str, relative_path: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "DELETE FROM scanned_files WHERE root_path = ? AND relative_path = ?",
                (root_path, relative_path),
            )
            conn.execute(
                "DELETE FROM scanned_folders WHERE root_path = ? AND relative_path = ?",
                (root_path, relative_path),
            )

    def enqueue_sync(self, payload: dict[str, Any]) -> int:
        now = time.time()
        blob = json.dumps(payload, ensure_ascii=False)
        with self._connect() as conn:
            cur = conn.execute(
                "INSERT INTO sync_queue (payload, status, created_at) VALUES (?, 'pending', ?)",
                (blob, now),
            )
            return int(cur.lastrowid)

    def pending_sync_batch(self, limit: int = 50) -> list[tuple[int, dict[str, Any]]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, payload FROM sync_queue WHERE status = 'pending' ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        out: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            out.append((row["id"], json.loads(row["payload"])))
        return out

    def mark_sync_done(self, queue_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM sync_queue WHERE id = ?", (queue_id,))

    def mark_sync_error(self, queue_id: int, error: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE sync_queue SET status = 'error', retries = retries + 1, last_error = ?
                WHERE id = ?
                """,
                (error[:2000], queue_id),
            )

    def state_get(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT value FROM scanner_state WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None

    def state_set(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scanner_state (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, value),
            )

    def clear_all(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                "DELETE FROM scanned_files; DELETE FROM scanned_folders; DELETE FROM sync_queue; DELETE FROM scanner_state;"
            )


def default_db_path(cwd: Path | None = None) -> Path:
    base = cwd or Path.cwd()
    return (base / "scanner.db").resolve()
