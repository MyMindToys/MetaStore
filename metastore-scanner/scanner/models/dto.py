"""Typed data transfer objects for scan results and sync payloads."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EntryKind(str, Enum):
    FILE = "file"
    FOLDER = "folder"


class Availability(str, Enum):
    PRESENT = "present"
    MISSING = "missing"


class SyncStatus(str, Enum):
    PENDING = "pending"
    SYNCED = "synced"
    ERROR = "error"


@dataclass(slots=True)
class DeviceInfo:
    machine_uid: str
    hostname: str
    os_name: str
    platform_name: str


@dataclass(slots=True)
class ScanEntry:
    """Single filesystem entry discovered during a scan."""

    kind: EntryKind
    absolute_path: str
    relative_path: str
    storage_root: str
    name: str
    size_bytes: int | None
    created_at_fs: datetime | None
    modified_at_fs: datetime | None
    extension: str
    checksum_sha256: str | None = None
    checksum_md5: str | None = None
    folder_file_count: int | None = None
    folder_total_size_bytes: int | None = None
    availability: Availability = Availability.PRESENT


@dataclass(slots=True)
class ScanBatch:
    """Batch payload for API upload."""

    device_machine_uid: str
    storage_location_root: str
    scanner_version: str
    entries: list[ScanEntry] = field(default_factory=list)
    deleted_relative_paths: list[str] = field(default_factory=list)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "device_machine_uid": self.device_machine_uid,
            "storage_location_root": self.storage_location_root,
            "scanner_version": self.scanner_version,
            "entries": [_entry_to_dict(e) for e in self.entries],
            "deleted_relative_paths": list(self.deleted_relative_paths),
        }


def _entry_to_dict(e: ScanEntry) -> dict[str, Any]:
    d: dict[str, Any] = {
        "kind": e.kind.value,
        "relative_path": e.relative_path,
        "name": e.name,
        "size_bytes": e.size_bytes,
        "created_at_fs": e.created_at_fs.isoformat() if e.created_at_fs else None,
        "modified_at_fs": e.modified_at_fs.isoformat() if e.modified_at_fs else None,
        "extension": e.extension,
        "checksum_sha256": e.checksum_sha256,
        "checksum_md5": e.checksum_md5,
        "availability": e.availability.value,
    }
    if e.kind == EntryKind.FOLDER:
        d["folder_file_count"] = e.folder_file_count
        d["folder_total_size_bytes"] = e.folder_total_size_bytes
    return d
