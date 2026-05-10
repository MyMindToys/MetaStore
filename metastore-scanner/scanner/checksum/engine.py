"""Checksum computation with chunked reads for large files."""

from __future__ import annotations

import hashlib
from pathlib import Path

DEFAULT_CHUNK = 1024 * 1024


def sha256_file(path: Path, chunk_size: int = DEFAULT_CHUNK) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def md5_file(path: Path, chunk_size: int = DEFAULT_CHUNK) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()
