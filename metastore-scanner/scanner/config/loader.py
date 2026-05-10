"""Load scanner configuration from YAML."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class ScannerConfig:
    server_url: str = "http://127.0.0.1:8000"
    scan_paths: list[str] = field(default_factory=list)
    exclude_patterns: list[str] = field(default_factory=list)
    calculate_checksums: bool = True
    checksum_md5: bool = False
    device_display_name: str | None = None
    #: Только уточнять пути из локальной базы, без полного обхода дерева (новые файлы не находятся).
    known_paths_only: bool = False
    #: Шаблоны имён файла (fnmatch по basename), только такие файлы ищутся под корнями — см. find_roots / scan_paths.
    find_names: list[str] = field(default_factory=list)
    #: Корни для режима find_names (если не пусто и задан find_names); иначе используются scan_paths.
    find_roots: list[str] = field(default_factory=list)
    #: При find_names — искать совпадения по диску; иначе только файлы уже в локальной базе (по умолчанию false).
    find_discover_on_disk: bool = False
    #: При полном инвентаре не заходить в служебные каталоги (__pycache__, .git, …).
    prune_artifact_dirs: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ScannerConfig:
        return cls(
            server_url=str(data.get("server_url", cls.server_url)),
            scan_paths=list(data.get("scan_paths") or []),
            exclude_patterns=list(data.get("exclude_patterns") or []),
            calculate_checksums=bool(data.get("calculate_checksums", True)),
            checksum_md5=bool(data.get("checksum_md5", False)),
            device_display_name=data.get("device_display_name"),
            known_paths_only=bool(data.get("known_paths_only", False)),
            find_names=list(data.get("find_names") or []),
            find_roots=list(data.get("find_roots") or []),
            prune_artifact_dirs=bool(data.get("prune_artifact_dirs", True)),
            find_discover_on_disk=bool(data.get("find_discover_on_disk", False)),
        )


def load_config(path: Path) -> ScannerConfig:
    text = path.read_text(encoding="utf-8")
    try:
        import yaml  # type: ignore
    except ImportError as exc:
        raise RuntimeError("Install PyYAML to use YAML config: pip install PyYAML") from exc
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("Config root must be a mapping")
    return ScannerConfig.from_dict(data)


def default_config_path() -> Path:
    return Path.cwd() / "scanner.yaml"
