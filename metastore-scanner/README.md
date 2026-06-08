# metastore-scanner

Лёгкий **CLI-агент** для локального сканирования файловой системы и отправки метаданных на **MetaStore Server** (Django REST API). Не использует Django ORM; локальный кэш — **SQLite** (`scanner.db` рядом с рабочей директорией или задаётся через код).

## Установка

```bash
cd metastore-scanner
python -m pip install -r requirements.txt
python -m pip install -e .
```

(`PyYAML` входит в зависимости пакета; нужен для `scanner.yaml`.)

Точка входа консоли: `metastore-scanner` (см. `[project.scripts]` в `pyproject.toml`). Альтернатива: `python -m scanner.cli` или `python main.py`.

Список всех подкоманд и ключей в терминале:

```bash
metastore-scanner --help
metastore-scanner scan --help
```

## Как запускать сканер (Windows / общее)

1. Активируйте виртуальное окружение, если ставили пакет в venv:

```powershell
cd metastore-scanner
.\venv\Scripts\activate
```

2. Запуск через модуль (надёжный способ):

```powershell
py -m scanner.cli scan
py -m scanner.cli device-info
```

или, если команда в PATH:

```powershell
metastore-scanner scan
```

3. Конфиг по умолчанию ищется как **`scanner.yaml`** в **текущей рабочей директории**; база кэша — **`scanner.db`** там же. Явный путь:

```powershell
py -m scanner.cli scan --config "D:\configs\scanner.yaml" --db "D:\configs\scanner.db"
```

4. Один каталог без YAML:

```powershell
py -m scanner.cli scan --path "C:\Users\you\Documents"
```

Без **`scanner.yaml`** результаты только в локальном **`scanner.db`**, на сервер не отправляются (в консоли будет предупреждение).

## Конфигурация (`scanner.yaml`)

Скопируйте пример и поправьте пути:

```bash
cp scanner.example.yaml scanner.yaml
```

### Поля YAML (основные)

| Поле | Назначение |
|------|------------|
| **`server_url`** | Базовый URL MetaStore (например `http://127.0.0.1:8000`). |
| **`scan_paths`** | Список корневых каталогов для полного скана (если не задан `--path` / `--find-root`). |
| **`exclude_patterns`** | Шаблоны `fnmatch` для исключения файлов/путей при обходе. |
| **`calculate_checksums`** | Считать SHA-256 для изменённых файлов (`true`/`false`). |
| **`checksum_md5`** | Дополнительно MD5 (редко нужно). |
| **`device_display_name`** | Имя устройства при регистрации на сервере. |
| **`known_paths_only`** | Только пути из локальной базы, без полного обхода дерева. |
| **`find_names`** | Шаблоны имён файлов (`fnmatch`), режим поиска по имени. |
| **`find_extensions`** | Список расширений без точки (`pdf`, `docx`) — то же, что шаблоны `*.pdf`, `*.docx`; можно сочетать с `find_names`. |
| **`find_roots`** | Отдельные корни для режима поиска (если не пусто — используются вместо `scan_paths` для поиска). |
| **`find_discover_on_disk`** | `true` — искать все совпадения на диске; `false` — по умолчанию только файлы уже в **`scanner.db`**. |
| **`prune_artifact_dirs`** | `true` — при полном инвентаре не заходить в `__pycache__`, `.git`, `node_modules`, `venv` и т.п. |

CLI-флаги перечислены ниже; многие дублируют или переопределяют YAML (см. описание у каждого ключа).

## Команды

| Команда | Описание |
|---------|----------|
| `device-info` | Вывести `machine_uid`, hostname, ОС (отладка регистрации). |
| `scan` | Сканирование; обновление **`scanner.db`**; при наличии **`scanner.yaml`** — синхронизация с сервером. |
| `sync` | Дослать очередь **`sync_queue`** на сервер. |
| `status` | Проверка `GET /api/v1/status/`. |
| `config` | Вывести разобранный YAML (`--path` к файлу). |
| `reset-cache` | Очистить таблицы кэша и очереди в SQLite (`--db` при необходимости). |

## Команда `scan`: ключи командной строки

Общие:

| Ключ | Описание |
|------|----------|
| **`--path`** `DIR` | Один корень сканирования (перекрывает `scan_paths` из YAML). |
| **`--config`** `FILE` | Путь к **`scanner.yaml`**. |
| **`--db`** `FILE` | Путь к **`scanner.db`**. |
| **`--no-recursive`** | Только один уровень каталога под корнем. |
| **`--no-checksum`** | Не считать хеши (перекрывает YAML, если не смешивать логику вручную). |
| **`--dry-run`** | Не писать в кэш и не хешировать; вывести JSON с результатом. |
| **`--verbose`** | Подробный лог. |
| **`--quiet`** | Без пошагового вывода в консоль (итоговая строка остаётся). |
| **`--progress-every`** `N` | Частота сообщений прогресса (по умолчанию 50). |

Инкремент и пересчёт:

| Ключ | Описание |
|------|----------|
| **`--full-rescan`** | Пересчитать SHA-256 для всех файлов под корнем. |
| **`--modified-after`** `ISO` | На сервер попадают только файлы с датой изменения ≥ даты (полный обход сохраняется). |
| **`--modified-before`** `ISO` | Верхняя граница `mtime` вместе с **`--modified-after`**. |

Режимы обхода и поиска:

| Ключ | Описание |
|------|----------|
| **`--no-prune-artifacts`** | Полный инвентарь заходит во **все** подпапки, включая `__pycache__`, `.git`, `node_modules`. По умолчанию такие ветки **обрезаются**. |
| **`--known-paths-only`** | Обрабатывать только пути из **`scanner.db`** для этого корня (новые файлы на диске не добавляются). |
| **`--find`** `PATTERN` | Шаблон имени файла (`fnmatch`: `*.pdf`, `Report_*`). Можно указать несколько раз. |
| **`--ext`** `EXT` | Только файлы с таким расширением (`pdf` или `.pdf`). Несколько раз: `--ext pdf --ext docx`. Дополняет **`--find`** и YAML. |
| **`--find-root`** `DIR` | Корни для поиска (несколько раз). Если не заданы — из YAML (`find_roots` или `scan_paths`). |
| **`--find-discover-all`** | Вместе с **`--find`** / **`--ext`**: искать **все** совпадения на диске под корнем. **Без** этого флага по умолчанию обрабатываются только файлы, **уже есть в локальной базе** под шаблоном. |
| **`--duplicate-warn-above`** `N` | Предупреждение в stderr, если одно имя файла в корне встречается больше `N` раз (`0` — отключить). Только для полного инвентаря без режима «только из кэша». |

Примеры:

```powershell
# Полный инвентарь по путям из scanner.yaml, синхронизация на сервер
py -m scanner.cli scan

# Один каталог, без лишнего вывода
py -m scanner.cli scan --path "D:\Work" --quiet

# Только PDF, уже учтённые в scanner.db (не обходить весь диск)
py -m scanner.cli scan --find "*.pdf" --path "C:\Users\you\Downloads"

# То же через расширение (можно несколько: --ext pdf --ext xlsx)
py -m scanner.cli scan --ext pdf --path "C:\Users\you\Downloads"

# Все PDF на диске под корнем (полное обнаружение)
py -m scanner.cli scan --ext pdf --find-discover-all --path "C:\Users\you\Downloads"

# Очистить локальный кэш и очередь
py -m scanner.cli reset-cache
```

## Архитектура модулей

- `scanner/device` — определение стабильного `machine_uid`.
- `scanner/filesystem` — обход только через `pathlib`, без shell.
- `scanner/checksum` — потоковое хеширование.
- `scanner/cache` — схема SQLite для инкрементального скана и офлайн-очереди.
- `scanner/api` — клиент `requests` с таймаутами и повторами.
- `scanner/sync` — постановка и сброс очереди.

## Сборка exe (Windows)

```powershell
pip install pyinstaller
.\scripts\build_pyinstaller.ps1
```

Убедитесь, что конфиг и `scanner.db` лежат рядом с бинарником при «portable» режиме или задайте рабочую директорию явно.
