"""CLI entrypoint for metastore-scanner."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from scanner import __version__
from scanner.cache.db import ScannerCache, default_db_path
from scanner.config.loader import ScannerConfig, default_config_path, load_config
from scanner.device.detector import detect_device
from scanner.filesystem.scanner import FilesystemScanner, ScanOptions
from scanner.models.dto import Availability, EntryKind, ScanBatch
from scanner.sync.service import SyncService, build_client, default_scanner_version
from scanner.utils.logging import setup_logging


def _parse_iso_datetime(s: str) -> datetime:
    raw = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _cmd_device_info(_args: argparse.Namespace) -> int:
    info = detect_device()
    print("Device:")
    print(f"  hostname: {info.hostname}")
    print(f"  machine_uid: {info.machine_uid}")
    print(f"  os: {info.os_name}")
    print(f"  platform: {info.platform_name}")
    return 0


def _cmd_config(args: argparse.Namespace) -> int:
    path = Path(args.path) if args.path else default_config_path()
    if not path.is_file():
        print(f"Config not found: {path}", file=sys.stderr)
        return 1
    cfg = load_config(path)
    print(json.dumps(cfg.__dict__, indent=2, default=str))
    return 0


def _cmd_status(args: argparse.Namespace) -> int:
    setup_logging(args.verbose)
    db_path = Path(args.db) if args.db else default_db_path()
    cache = ScannerCache(db_path)
    cache.init_schema()
    cfg_path = Path(args.config) if args.config else default_config_path()
    server_url = "http://127.0.0.1:8000"
    token = cache.state_get("scanner_token")
    if cfg_path.is_file():
        cfg = load_config(cfg_path)
        server_url = cfg.server_url
    client = build_client(server_url, token)
    try:
        data = client.get_server_status()
        print(json.dumps(data, indent=2))
    except Exception as exc:
        print(f"Server unreachable: {exc}", file=sys.stderr)
        return 1
    return 0


def _cmd_reset_cache(args: argparse.Namespace) -> int:
    db_path = Path(args.db) if args.db else default_db_path()
    cache = ScannerCache(db_path)
    cache.init_schema()
    cache.clear_all()
    print(f"Cache cleared: {db_path}")
    return 0


def _ensure_registered(cache: ScannerCache, cfg: ScannerConfig) -> str | None:
    token = cache.state_get("scanner_token")
    if token:
        return token
    info = detect_device()
    client = build_client(cfg.server_url, None)
    display = cfg.device_display_name or info.hostname
    data = client.register_device(
        machine_uid=info.machine_uid,
        hostname=info.hostname,
        os_name=info.os_name,
        platform_name=info.platform_name,
        display_name=display,
    )
    token = str(data.get("scanner_token", ""))
    if not token:
        print("Registration response missing scanner_token", file=sys.stderr)
        return None
    cache.state_set("scanner_token", token)
    return token


def _cmd_scan(args: argparse.Namespace) -> int:
    setup_logging(args.verbose)
    db_path = Path(args.db) if args.db else default_db_path()
    cache = ScannerCache(db_path)
    cache.init_schema()

    cfg_path = Path(args.config) if args.config else default_config_path()
    exclude: tuple[str, ...] = ()
    calculate_checksums = not args.no_checksum
    cfg = None
    if cfg_path.is_file():
        cfg = load_config(cfg_path)
        exclude = tuple(cfg.exclude_patterns)
        calculate_checksums = cfg.calculate_checksums if not args.no_checksum else False

    find_cli = tuple(dict.fromkeys(getattr(args, "find", None) or ()))
    find_cfg = tuple(cfg.find_names) if cfg else ()
    find_patterns = tuple(dict.fromkeys(list(find_cfg) + list(find_cli)))

    find_root_cli = [Path(p) for p in (getattr(args, "find_root", None) or [])]

    roots: list[Path] = []
    if args.path:
        roots.append(Path(args.path))
    elif find_root_cli:
        roots = find_root_cli
    elif cfg is not None:
        if find_patterns and cfg.find_roots:
            roots = [Path(p) for p in cfg.find_roots]
        else:
            roots = [Path(p) for p in cfg.scan_paths]
    if not roots:
        print(
            "No paths: pass --path, --find-root, or configure scan_paths / find_roots in scanner.yaml",
            file=sys.stderr,
        )
        return 1

    m_after = _parse_iso_datetime(args.modified_after) if getattr(args, "modified_after", None) else None
    m_before = _parse_iso_datetime(args.modified_before) if getattr(args, "modified_before", None) else None

    quiet = getattr(args, "quiet", False)
    prog_every = getattr(args, "progress_every", 50) or 50
    if prog_every < 1:
        prog_every = 1
    dup_thr = getattr(args, "duplicate_warn_above", 20)
    if dup_thr < 0:
        dup_thr = 0

    known_paths_only = bool(getattr(args, "known_paths_only", False))
    if cfg is not None:
        known_paths_only = known_paths_only or cfg.known_paths_only

    if known_paths_only and find_patterns:
        print(
            "Нельзя одновременно --known-paths-only и поиск по имени (--find / find_names в YAML).",
            file=sys.stderr,
        )
        return 1

    find_discover_on_disk = bool(getattr(args, "find_discover_all", False))
    if cfg is not None:
        find_discover_on_disk = find_discover_on_disk or cfg.find_discover_on_disk

    no_prune_cli = bool(getattr(args, "no_prune_artifacts", False))
    if cfg is not None:
        prune_artifacts = cfg.prune_artifact_dirs and not no_prune_cli
    else:
        prune_artifacts = not no_prune_cli

    opts = ScanOptions(
        recursive=not args.no_recursive,
        calculate_checksums=calculate_checksums,
        checksum_md5=False,
        exclude_patterns=exclude,
        dry_run=args.dry_run,
        full_rescan=args.full_rescan,
        mtime_after=m_after,
        mtime_before=m_before,
        show_progress=not quiet,
        progress_every=prog_every,
        duplicate_basename_warn_threshold=dup_thr,
        known_paths_only=known_paths_only,
        find_name_patterns=find_patterns,
        find_discover_on_disk=find_discover_on_disk,
        prune_artifact_dirs=prune_artifacts,
    )

    if not quiet:
        print("Запуск сканирования…", flush=True)

    scanner = FilesystemScanner()
    info = detect_device()
    all_deleted: list[str] = []
    batches: list[ScanBatch] = []

    for root in roots:
        try:
            entries, deleted = scanner.scan_root(root, cache, opts)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        all_deleted.extend(deleted)
        present_entries = [e for e in entries if e.availability == Availability.PRESENT]
        batch = ScanBatch(
            device_machine_uid=info.machine_uid,
            storage_location_root=str(root.resolve()),
            scanner_version=default_scanner_version(),
            entries=present_entries,
            deleted_relative_paths=deleted,
        )
        batches.append(batch)

    n_upload = sum(len(b.entries) for b in batches)
    n_del = sum(len(b.deleted_relative_paths) for b in batches)
    if quiet:
        print(
            f"Готово локально: записей для отправки {n_upload}, удалённых путей {n_del}.",
            flush=True,
        )
    else:
        print("---")
        print("Что сделано локально:")
        for r in roots:
            print(f"  Обойден каталог: {r.resolve()}")
        print(f"  Записей для отправки на сервер (файлы и папки): {n_upload}")
        print(f"  Путей, помеченных как исчезнувшие с диска: {n_del}")
        if opts.full_rescan:
            print("  Режим: полный пересчёт SHA-256 для файлов (флаг --full-rescan).")
        if opts.mtime_after or opts.mtime_before:
            print("  Режим: на сервер только файлы/папки с датой изменения в заданном окне.")
        elif not opts.full_rescan:
            print("  Режим: обычный (хеш только для новых/изменённых по размеру и дате).")
        if opts.known_paths_only:
            print("  Режим: только пути из локального кэша (полного обхода каталога нет).")
        if opts.find_name_patterns:
            if opts.find_discover_on_disk:
                print(
                    f"  Режим: поиск по имени по диску (fnmatch): {', '.join(opts.find_name_patterns)} "
                    "(--find-discover-all или find_discover_on_disk в YAML)."
                )
            else:
                print(
                    f"  Режим: только файлы из локальной базы под шаблонами: {', '.join(opts.find_name_patterns)} "
                    "(полный поиск по диску: --find-discover-all)."
                )
        if not opts.known_paths_only and not opts.find_name_patterns and opts.prune_artifact_dirs:
            print("  Обход: служебные подпапки (__pycache__, .git, node_modules, venv, …) пропускаются.")
        elif not opts.known_paths_only and not opts.find_name_patterns and not opts.prune_artifact_dirs:
            print("  Обход: без отсечения веток (--no-prune-artifacts).")
        print("---")

    if args.dry_run:
        print(json.dumps([b.to_json_dict() for b in batches], indent=2, default=str))
        return 0

    if m_after or m_before:
        print(
            "Период по дате изменения: полный обход диска, на сервер уходят только файлы (и при необходимости папки) с mtime в заданном окне.",
        )

    if cfg_path.is_file():
        if cfg is None:
            cfg = load_config(cfg_path)
        token = _ensure_registered(cache, cfg)
        if not token:
            return 1
        if not quiet:
            print("Отправка на сервер…", flush=True)
        client = build_client(cfg.server_url, token)
        sync = SyncService(cache, client)
        for batch in batches:
            sync.enqueue_batch(batch)
        ok, err = sync.flush_queue(limit=100)
        print(f"Отправка завершена: успешно {ok}, ошибок {err}.", flush=True)
        try:
            client.send_heartbeat(info.machine_uid, default_scanner_version())
        except Exception as exc:
            print(f"Heartbeat failed: {exc}", file=sys.stderr)
    else:
        print("No scanner.yaml — results kept in local cache only. Create scanner.yaml to sync.")

    return 0


def _cmd_sync(args: argparse.Namespace) -> int:
    setup_logging(args.verbose)
    db_path = Path(args.db) if args.db else default_db_path()
    cache = ScannerCache(db_path)
    cache.init_schema()
    cfg_path = Path(args.config) if args.config else default_config_path()
    if not cfg_path.is_file():
        print(f"Missing config {cfg_path}", file=sys.stderr)
        return 1
    cfg = load_config(cfg_path)
    token = _ensure_registered(cache, cfg)
    if not token:
        return 1
    client = build_client(cfg.server_url, token)
    sync = SyncService(cache, client)
    ok, err = sync.flush_queue(limit=500)
    print(f"sync: ok={ok} errors={err}")
    info = detect_device()
    try:
        client.send_heartbeat(info.machine_uid, default_scanner_version())
    except Exception as exc:
        print(f"Heartbeat failed: {exc}", file=sys.stderr)
    return 0 if err == 0 else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="metastore-scanner", description="MetaStore filesystem scanner agent")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = p.add_subparsers(dest="command", required=True)

    s_dev = sub.add_parser("device-info", help="Print detected device fingerprint")
    s_dev.set_defaults(func=_cmd_device_info)

    s_cfg = sub.add_parser("config", help="Show parsed scanner.yaml")
    s_cfg.add_argument("--path", type=str, default=None, help="Path to scanner.yaml")
    s_cfg.set_defaults(func=_cmd_config)

    s_st = sub.add_parser("status", help="Server status (GET /api/v1/status/)")
    s_st.add_argument("--config", type=str, default=None, help="scanner.yaml (for server_url override)")
    s_st.add_argument("--db", type=str, default=None)
    s_st.add_argument("--verbose", action="store_true")
    s_st.set_defaults(func=_cmd_status)

    s_rs = sub.add_parser("reset-cache", help="Wipe local SQLite cache")
    s_rs.add_argument("--db", type=str, default=None)
    s_rs.set_defaults(func=_cmd_reset_cache)

    s_scan = sub.add_parser("scan", help="Scan paths and optionally sync to server")
    s_scan.add_argument("--path", type=str, default=None, help="Directory to scan")
    s_scan.add_argument("--config", type=str, default=None, help="scanner.yaml path")
    s_scan.add_argument("--db", type=str, default=None)
    s_scan.add_argument("--no-recursive", action="store_true")
    s_scan.add_argument("--no-checksum", action="store_true")
    s_scan.add_argument("--dry-run", action="store_true")
    s_scan.add_argument("--verbose", action="store_true")
    s_scan.add_argument(
        "--full-rescan",
        action="store_true",
        help="Пересчитать SHA-256 для всех файлов (иначе используется кэш, если размер/mtime не менялись).",
    )
    s_scan.add_argument(
        "--modified-after",
        type=str,
        default=None,
        metavar="ISO",
        help="Инкрементальный режим: на сервер уходят только файлы с mtime ≥ этой даты (ISO 8601, напр. 2025-01-15 или 2025-01-15T12:00:00Z). Обход дерева полный.",
    )
    s_scan.add_argument(
        "--modified-before",
        type=str,
        default=None,
        metavar="ISO",
        help="Верхняя граница mtime (вместе с --modified-after задаёт окно).",
    )
    s_scan.add_argument(
        "--quiet",
        action="store_true",
        help="Не показывать ход работы (для скриптов).",
    )
    s_scan.add_argument(
        "--progress-every",
        type=int,
        default=50,
        metavar="N",
        help="Как часто печатать прогресс при обходе и разборе файлов (по умолчанию 50).",
    )
    s_scan.add_argument(
        "--duplicate-warn-above",
        type=int,
        default=20,
        metavar="N",
        help="В stderr — предупреждение, если одно имя файла в корне встречается больше N раз (0 — отключить).",
    )
    s_scan.add_argument(
        "--known-paths-only",
        action="store_true",
        help="Не обходить всё дерево: только пути из локальной базы (scanner.db). Новые файлы не находятся.",
    )
    s_scan.add_argument(
        "--find",
        action="append",
        metavar="PATTERN",
        help="Искать только файлы, basename совпадает с шаблоном fnmatch (напр. *.pdf, README*). Повторите для нескольких.",
    )
    s_scan.add_argument(
        "--find-root",
        action="append",
        metavar="DIR",
        help="Каталоги, где искать (можно несколько). Если не указано — из scanner.yaml: find_roots или scan_paths.",
    )
    s_scan.add_argument(
        "--find-discover-all",
        action="store_true",
        help="Вместе с —find: искать все совпадения на диске под корнем. Иначе по умолчанию только файлы уже в локальной базе (scanner.db).",
    )
    s_scan.add_argument(
        "--no-prune-artifacts",
        action="store_true",
        help="При полном инвентаре заходить во все подпапки (в т.ч. __pycache__, .git, node_modules). Иначе они пропускаются.",
    )
    s_scan.set_defaults(func=_cmd_scan)

    s_sync = sub.add_parser("sync", help="Flush offline sync queue")
    s_sync.add_argument("--config", type=str, default=None)
    s_sync.add_argument("--db", type=str, default=None)
    s_sync.add_argument("--verbose", action="store_true")
    s_sync.set_defaults(func=_cmd_sync)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
