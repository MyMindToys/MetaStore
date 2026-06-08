"""Recursive filesystem scanning with incremental checksum strategy."""

from __future__ import annotations

import fnmatch
import os
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator

from scanner.cache.db import ScannerCache
from scanner.checksum.engine import md5_file, sha256_file
from scanner.models.dto import Availability, EntryKind, ScanEntry
from scanner.utils.logging import get_logger

logger = get_logger(__name__)


def mtime_ns_from_stat(st: os.stat_result) -> int:
    ns = getattr(st, "st_mtime_ns", None)
    if ns is not None:
        return int(ns)
    return int(st.st_mtime * 1_000_000_000)


@dataclass(slots=True)
class ScanOptions:
    recursive: bool = True
    calculate_checksums: bool = True
    checksum_md5: bool = False
    exclude_patterns: tuple[str, ...] = ()
    dry_run: bool = False
    full_rescan: bool = False
    #: Если задано — на сервер попадают только файлы, у которых mtime попадает в интервал (полный обход диска сохраняется).
    mtime_after: datetime | None = None
    mtime_before: datetime | None = None
    #: Прогресс в консоль (иначе долго тишина).
    show_progress: bool = True
    #: Как часто выводить счётчик во время обхода / обработки (файлов).
    progress_every: int = 50
    #: Если одно имя файла (без пути) встречается в корне чаще — предупреждение в stderr (0 = выкл.).
    duplicate_basename_warn_threshold: int = 20
    #: Не делать полный обход диска — только пути, уже есть в локальной базе для этого корня.
    known_paths_only: bool = False
    #: Имена файлов (fnmatch по basename), например "*.pdf", "README*"; пусто = полный инвентарный обход.
    find_name_patterns: tuple[str, ...] = ()
    #: Если задан find — искать совпадения по всему диску под корнем; иначе только файлы уже в локальной базе (scanned_files).
    find_discover_on_disk: bool = False
    #: При полном инвентаре не заходить в типичные служебные каталоги (__pycache__, .git, node_modules, …).
    prune_artifact_dirs: bool = True


def _emit_file_by_period(modified_at_fs: datetime | None, options: ScanOptions) -> bool:
    if options.mtime_after is None and options.mtime_before is None:
        return True
    if modified_at_fs is None:
        return False
    if options.mtime_after is not None and modified_at_fs < options.mtime_after:
        return False
    if options.mtime_before is not None and modified_at_fs > options.mtime_before:
        return False
    return True


def _say(opts: ScanOptions, msg: str) -> None:
    if opts.show_progress:
        print(msg, flush=True)
        try:
            sys.stdout.flush()
        except Exception:
            pass


def _warn_duplicate_basenames(
    file_rows: list[tuple[str, Path, os.stat_result]],
    root_str: str,
    threshold: int,
) -> None:
    if threshold <= 0 or not file_rows:
        return
    counts = Counter(p.name for _rel, p, _st in file_rows)
    hot = sorted(
        ((n, c) for n, c in counts.items() if c > threshold),
        key=lambda x: (-x[1], x[0].lower()),
    )
    if not hot:
        return
    print(
        "\nВНИМАНИЕ: под этим корнем одно и то же имя файла встречается много раз "
        f"(больше {threshold}). Имя без пути не однозначно — проверьте, что в конфиге указана "
        "именно та папка, которую вы имели в виду.",
        file=sys.stderr,
        flush=True,
    )
    max_lines = 12
    for name, cnt in hot[:max_lines]:
        print(
            f"  • «{name}» — {cnt} файлов с таким именем в {root_str}",
            file=sys.stderr,
            flush=True,
        )
    if len(hot) > max_lines:
        print(
            f"  … и ещё {len(hot) - max_lines} имён с большим числом совпадений.",
            file=sys.stderr,
            flush=True,
        )


def _is_excluded(rel_posix: str, name: str, patterns: Iterable[str]) -> bool:
    for pat in patterns:
        if fnmatch.fnmatch(name, pat) or fnmatch.fnmatch(rel_posix, pat):
            return True
        if "/" in pat and fnmatch.fnmatch(rel_posix, pat):
            return True
    return False


def _basename_matches_find(rel_posix: str, patterns: tuple[str, ...]) -> bool:
    base = Path(rel_posix).name
    return any(fnmatch.fnmatch(base, pat) for pat in patterns)


# Каталоги, в которые при полном обходе не спускаемся (иначе rglob лезет во всё подряд).
DEFAULT_PRUNE_DIR_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        ".git",
        ".svn",
        ".hg",
        "node_modules",
        ".pnpm-store",
        ".yarn",
        ".venv",
        "venv",
        ".mypy_cache",
        ".pytest_cache",
        ".tox",
        ".nox",
        ".hypothesis",
        "dist",
        "build",
        ".eggs",
        ".gradle",
        "site-packages",
        "__MACOSX",
    }
)


def _should_prune_dir(dirname: str) -> bool:
    if dirname in DEFAULT_PRUNE_DIR_NAMES:
        return True
    if dirname.endswith(".egg-info"):
        return True
    return False


def _iter_inventory_paths(
    root: Path,
    *,
    recursive: bool,
    prune_artifacts: bool,
) -> Iterator[Path]:
    """Обход для полного инвентаря: при prune не заходит в типичный «мусор» разработки."""
    root = root.resolve()
    if not recursive:
        yield from root.iterdir()
        return
    if not prune_artifacts:
        yield from root.rglob("*")
        return

    for dirpath, dirnames, filenames in os.walk(str(root), topdown=True):
        dpath = Path(dirpath)
        dirnames[:] = [dn for dn in dirnames if not _should_prune_dir(dn)]

        if dpath != root:
            yield dpath

        for fn in filenames:
            yield dpath / fn


class FilesystemScanner:
    """Walks paths using pathlib only (no shell)."""

    def scan_root(
        self,
        root: Path,
        cache: ScannerCache,
        options: ScanOptions,
    ) -> tuple[list[ScanEntry], list[str]]:
        root = root.expanduser().resolve()
        if not root.is_dir():
            raise FileNotFoundError(f"Not a directory: {root}")

        root_str = str(root)
        previous = cache.list_cached_paths_for_root(root_str)
        seen: set[str] = set()

        file_rows: list[tuple[str, Path, os.stat_result]] = []
        dir_paths: list[Path] = []

        if options.known_paths_only and options.find_name_patterns:
            raise ValueError(
                "Нельзя совместить --known-paths-only и поиск по имени (--find / find_names)."
            )

        every = max(1, options.progress_every)
        _say(options, f"Сканирование запущено: {root_str}")

        walk_i = 0
        if options.known_paths_only:
            if not previous:
                raise ValueError(
                    "Для этого корня в локальной базе нет путей — сначала выполните полное сканирование "
                    "без режима «только из кэша» (--known-paths-only / known_paths_only в YAML)."
                )
            _say(
                options,
                "Режим «только из кэша»: проверяются только пути из локальной базы; полного обхода дерева нет; "
                "новые файлы на диске не добавятся, пока не сделаете обычное сканирование.",
            )
            _say(options, f"Проверка известных путей из базы, всего {len(previous)}…")
            for rel in sorted(previous):
                walk_i += 1
                if options.show_progress and walk_i % every == 0:
                    _say(options, f"  … проверено из кэша: {walk_i}/{len(previous)}")
                path = root if rel in ("", ".") else (root / rel)
                try:
                    if not path.exists():
                        continue
                    st = path.stat()
                except OSError as exc:
                    logger.warning("stat failed for %s: %s", path, exc)
                    continue

                if path.is_dir():
                    dir_paths.append(path)
                    seen.add(rel)
                elif path.is_file():
                    file_rows.append((rel, path, st))
                    seen.add(rel)

            _say(
                options,
                f"Проверка из кэша завершена: обработано записей {walk_i}, файлов {len(file_rows)}, каталогов {len(dir_paths)}.",
            )
        elif options.find_name_patterns:
            shown = ", ".join(options.find_name_patterns)
            if options.find_discover_on_disk:
                _say(
                    options,
                    f"Поиск по имени по диску (шаблоны: {shown}). Полный обход совпадений glob под корнем.",
                )
                matched: dict[str, tuple[Path, os.stat_result]] = {}
                globber = root.rglob if options.recursive else root.glob
                for pat in options.find_name_patterns:
                    try:
                        candidates = globber(pat)
                    except (OSError, ValueError) as exc:
                        logger.warning("glob failed pattern %r under %s: %s", pat, root, exc)
                        continue
                    for path in candidates:
                        walk_i += 1
                        if options.show_progress and walk_i % every == 0:
                            _say(options, f"  … просмотрено совпадений (до отсева): {walk_i}")
                        if not path.is_file():
                            continue
                        try:
                            rel = path.relative_to(root).as_posix()
                        except ValueError:
                            continue
                        name = path.name
                        if _is_excluded(rel, name, options.exclude_patterns):
                            continue
                        try:
                            st = path.stat()
                        except OSError as exc:
                            logger.warning("stat failed for %s: %s", path, exc)
                            continue
                        matched[rel] = (path, st)

                for rel, (_p, _st) in matched.items():
                    seen.add(rel)
                    parts = rel.split("/")
                    for i in range(len(parts) - 1):
                        prefix = "/".join(parts[: i + 1])
                        seen.add(prefix)
                        dpath = root / prefix
                        try:
                            if dpath.is_dir():
                                dir_paths.append(dpath)
                        except OSError:
                            pass

                dir_paths = sorted(set(dir_paths), key=lambda p: str(p))
                file_rows = [(rel, p, st) for rel, (p, st) in sorted(matched.items())]

                _say(
                    options,
                    f"Поиск по диску завершён: найдено файлов {len(file_rows)}, затронуто каталогов {len(dir_paths)}.",
                )
            else:
                cached_files = cache.list_cached_file_paths_for_root(root_str)
                to_scan = sorted(
                    rel
                    for rel in cached_files
                    if _basename_matches_find(rel, options.find_name_patterns)
                )
                _say(
                    options,
                    f"Поиск только среди файлов уже в локальной базе (шаблоны: {shown}), подошло путей: {len(to_scan)}. "
                    "Чтобы искать все совпадения на диске, используйте --find-discover-all.",
                )
                for rel in to_scan:
                    walk_i += 1
                    if options.show_progress and walk_i % every == 0:
                        _say(options, f"  … обработано из кэша: {walk_i}/{len(to_scan)}")
                    path = root / rel if rel not in ("", ".") else root
                    if _is_excluded(rel, path.name, options.exclude_patterns):
                        continue
                    try:
                        if not path.is_file():
                            continue
                        st = path.stat()
                    except OSError as exc:
                        logger.warning("stat failed for %s: %s", path, exc)
                        continue
                    file_rows.append((rel, path, st))
                    seen.add(rel)

                for rel, _p, _st in file_rows:
                    parts = rel.split("/")
                    for i in range(len(parts) - 1):
                        prefix = "/".join(parts[: i + 1])
                        seen.add(prefix)
                        dpath = root / prefix
                        try:
                            if dpath.is_dir():
                                dir_paths.append(dpath)
                        except OSError:
                            pass

                dir_paths = sorted(set(dir_paths), key=lambda p: str(p))

                _say(
                    options,
                    f"Готово: обновлено файлов из базы под шаблоны — {len(file_rows)}, каталогов — {len(dir_paths)}.",
                )
        else:
            if options.prune_artifact_dirs:
                _say(
                    options,
                    "Обход каталога (полный инвентарь; служебные папки вроде __pycache__, .git, "
                    "node_modules, venv не обходятся — см. --no-prune-artifacts).",
                )
            else:
                _say(
                    options,
                    "Обход каталога (полный инвентарь без отсечения веток — заходит во все подпапки).",
                )

            iterator = _iter_inventory_paths(
                root,
                recursive=options.recursive,
                prune_artifacts=options.prune_artifact_dirs,
            )
            for path in iterator:
                walk_i += 1
                if options.show_progress and walk_i % every == 0:
                    _say(options, f"  … обход: просмотрено элементов {walk_i}")
                try:
                    rel = path.relative_to(root).as_posix()
                except ValueError:
                    continue
                name = path.name
                if _is_excluded(rel, name, options.exclude_patterns):
                    continue
                try:
                    st = path.stat()
                except OSError as exc:
                    logger.warning("stat failed for %s: %s", path, exc)
                    continue

                if path.is_dir():
                    dir_paths.append(path)
                    seen.add(rel)
                    continue

                if path.is_file():
                    file_rows.append((rel, path, st))
                    seen.add(rel)

            _say(
                options,
                f"Обход завершён: просмотрено элементов {walk_i}, файлов {len(file_rows)}, каталогов {len(dir_paths)}.",
            )

            _warn_duplicate_basenames(
                file_rows,
                root_str,
                options.duplicate_basename_warn_threshold,
            )

        # Recursive file count / total bytes per folder prefix
        folder_stats: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
        for rel, _path, st in file_rows:
            size = int(st.st_size)
            parts = rel.split("/")
            for i in range(len(parts) - 1):
                prefix = "/".join(parts[: i + 1])
                c, s = folder_stats[prefix]
                folder_stats[prefix] = (c + 1, s + size)

        entries: list[ScanEntry] = []

        total_files = len(file_rows)
        if total_files:
            _say(options, f"Обработка файлов (метаданные и SHA-256 при необходимости), всего {total_files}…")

        for fi, (rel, path, st) in enumerate(file_rows):
            mtime_ns = mtime_ns_from_stat(st)
            size_b = int(st.st_size)
            ext = path.suffix.lstrip(".") if path.suffix else ""

            cached = cache.get_cached_file(root_str, rel)
            need_checksum = options.calculate_checksums and (
                options.full_rescan
                or cached is None
                or cached.size_bytes != size_b
                or cached.mtime_ns != mtime_ns
                or not cached.checksum_sha256
            )

            will_hash = bool(
                options.calculate_checksums and need_checksum and not options.dry_run
            )
            if options.show_progress and total_files:
                if fi == 0 or (fi + 1) % every == 0 or (fi + 1) == total_files:
                    short = rel if len(rel) <= 90 else rel[:87] + "..."
                    mark = "хеш" if will_hash else "кэш"
                    _say(
                        options,
                        f"  [{fi + 1}/{total_files}] ({mark}) {short}",
                    )

            checksum_sha: str | None = None
            checksum_m: str | None = None
            if will_hash:
                if options.show_progress:
                    _say(
                        options,
                        f"      → SHA-256, {size_b} байт…",
                    )
                checksum_sha = sha256_file(path)
                if options.checksum_md5:
                    checksum_m = md5_file(path)
            elif cached and cached.checksum_sha256 and not options.full_rescan:
                checksum_sha = cached.checksum_sha256

            created = getattr(st, "st_ctime", None)
            created_dt = (
                datetime.fromtimestamp(created, tz=timezone.utc) if created else None
            )
            modified_dt = datetime.fromtimestamp(
                st.st_mtime,
                tz=timezone.utc,
            )

            entry = ScanEntry(
                kind=EntryKind.FILE,
                absolute_path=str(path),
                relative_path=rel,
                storage_root=root_str,
                name=path.name,
                size_bytes=size_b,
                created_at_fs=created_dt,
                modified_at_fs=modified_dt,
                extension=ext,
                checksum_sha256=checksum_sha,
                checksum_md5=checksum_m,
                availability=Availability.PRESENT,
            )

            if not options.dry_run:
                cache.upsert_file(
                    root_str,
                    rel,
                    EntryKind.FILE.value,
                    size_b,
                    mtime_ns,
                    checksum_sha,
                )

            if _emit_file_by_period(modified_dt, options):
                entries.append(entry)

        if total_files:
            _say(options, "Обработка файлов завершена.")

        # Folder entries
        if dir_paths and options.show_progress:
            _say(options, f"Записи о каталогах ({len(dir_paths)})…")
        for folder in sorted(dir_paths, key=lambda p: str(p)):
            rel = folder.relative_to(root).as_posix()
            try:
                st = folder.stat()
            except OSError:
                continue
            mtime_ns = mtime_ns_from_stat(st)
            if rel in folder_stats:
                fc, total = folder_stats[rel]
            elif options.known_paths_only or options.find_name_patterns:
                alt = cache.get_cached_folder_stats(root_str, rel if rel else ".")
                fc, total = alt if alt is not None else (0, 0)
            else:
                fc, total = (0, 0)
            entry = ScanEntry(
                kind=EntryKind.FOLDER,
                absolute_path=str(folder),
                relative_path=rel if rel else ".",
                storage_root=root_str,
                name=folder.name or ".",
                size_bytes=None,
                created_at_fs=None,
                modified_at_fs=datetime.fromtimestamp(st.st_mtime, tz=timezone.utc),
                extension="",
                checksum_sha256=None,
                folder_file_count=fc,
                folder_total_size_bytes=total,
                availability=Availability.PRESENT,
            )
            if not options.dry_run:
                cache.upsert_folder(root_str, rel if rel else ".", fc, total, mtime_ns)

            period = options.mtime_after is not None or options.mtime_before is not None
            if not period:
                entries.append(entry)
            elif _emit_file_by_period(entry.modified_at_fs, options):
                entries.append(entry)

        if options.find_name_patterns:
            prev_matching = {p for p in previous if _basename_matches_find(p, options.find_name_patterns)}
            deleted_rel = sorted(prev_matching - seen)
        else:
            deleted_rel = sorted(previous - seen)
        if deleted_rel and options.show_progress:
            _say(options, f"Пути, которых больше нет на диске: {len(deleted_rel)}…")
        for rel in deleted_rel:
            if not options.dry_run:
                cache.delete_path_entry(root_str, rel)
            entries.append(
                ScanEntry(
                    kind=EntryKind.FILE,
                    absolute_path="",
                    relative_path=rel,
                    storage_root=root_str,
                    name=Path(rel).name,
                    size_bytes=None,
                    created_at_fs=None,
                    modified_at_fs=None,
                    extension="",
                    checksum_sha256=None,
                    availability=Availability.MISSING,
                )
            )

        return entries, deleted_rel
