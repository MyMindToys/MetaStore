# MetaStore — техническое описание: архитектура и код

Документ предназначен для разработчиков и сопровождения системы. Описывает границы ответственности компонентов, потоки данных, ключевые модули и точки расширения. Поверхностный обзор см. также в [DESCRIPTION.md](DESCRIPTION.md); пользовательские сценарии — в [USER_GUIDE.md](USER_GUIDE.md).

---

## 1. Назначение и границы системы

**MetaStore** — централизованный каталог **метаданных** о файлах и их расположении на устройствах. Сервер **не принимает и не хранит содержимое файлов** (бинарные загрузки не являются частью протокола сканера). На сервер передаются сведения об имени, относительном пути, размере, датах из ФС, SHA-256 (если включено на агенте), идентификаторе устройства и корне сканирования.

Архитектура **двухкомпонентная**:

| Компонент | Расположение в репозитории | Роль |
|-----------|----------------------------|------|
| **Сервер** | Корень (`manage.py`, приложение `catalog`) | Django + DRF, БД, веб-UI, REST API |
| **Агент сканирования** | `metastore-scanner/` | CLI: обход локальной ФС, локальный SQLite-кэш, отправка пакетов на API |

Поток данных по умолчанию: **локальный диск → metastore-scanner → HTTPS/HTTP → Django REST → PostgreSQL или SQLite**.

---

## 2. Структура репозитория (ориентир для навигации)

```
metastore/
├── manage.py
├── requirements.txt              # зависимости сервера
├── metastore/
│   ├── settings.py               # БД, SECRET_KEY, ALLOWED_HOSTS, USE_SQLITE
│   ├── urls.py                   # /admin/, /api/v1/, корень → catalog
│   └── wsgi.py / asgi.py
├── catalog/                      # основное Django-приложение
│   ├── models.py                 # доменные модели (см. §4)
│   ├── views.py                  # шаблонные представления (в т.ч. ScanInbox)
│   ├── forms.py
│   ├── api_views.py              # REST для сканера и списков
│   ├── api_serializers.py
│   ├── api_urls.py               # маршруты под /api/v1/
│   ├── authentication.py       # Scanner token (DRF)
│   ├── admin.py
│   └── migrations/
├── catalog/templates/catalog/    # Bootstrap UI
└── metastore-scanner/            # отдельный installable package
    ├── pyproject.toml / setup / requirements.txt
    ├── scanner/
    │   ├── cli.py                # точка входа CLI, сборка ScanOptions
    │   ├── config/loader.py     # ScannerConfig из YAML
    │   ├── cache/db.py          # SQLite: scanned_*, sync_queue, scanner_state
    │   ├── filesystem/scanner.py # FilesystemScanner, ScanOptions
    │   ├── checksum/engine.py   # потоковый SHA-256 / MD5
    │   ├── device/detector.py   # machine_uid и отпечаток ОС
    │   ├── models/dto.py        # ScanEntry, ScanBatch
    │   ├── api/client.py        # HTTP-клиент к серверу
    │   └── sync/service.py      # очередь синхронизации
    ├── scanner.example.yaml
    └── README.md                 # справка по флагам CLI (дублирует часть §7)
```

---

## 3. Сервер: стек и конфигурация

- **Django** (проект ориентирован на LTS-линию, см. `requirements.txt`).
- **Django REST Framework** для JSON API.
- **БД**: PostgreSQL через переменные окружения `POSTGRES_*` или файл **`db.sqlite3`** при установке **`USE_SQLITE=1`** (см. `metastore/settings.py`).

Критичные переменные окружения (типичный прод):

- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
- параметры PostgreSQL при отключённом SQLite

Веб-маршрутизация (`metastore/urls.py`):

- `/admin/` — стандартная админка Django;
- `/api/v1/` — включает `catalog.api_urls`;
- `` — все публичные страницы каталога из `catalog.urls` (поиск, материалы, «Разбор скана», справка по сканеру и т.д.).

**Примечание по безопасности:** в текущей версии веб-представления каталога не обёрнуты в обязательную аутентификацию сессии — развёртывание предполагается в доверенной сети или за обратным прокси с SSO; при выводе в интернет следует добавить middleware/login или внешнюю защиту.

---

## 4. Модели данных (домен)

### 4.1 Устройства и корни сканирования

- **`Device`** — логическое устройство агента: имя, тип, `machine_uid` (стабильный идентификатор с клиента), `hostname`, ОС, **`scanner_token`** (секрет после регистрации, уникальный).
- **`StorageLocation`** — пара `(device, root_path)`: зарегистрированный **корень** сканирования (абсолютный путь на стороне клиента, как строка).

Ограничение уникальности: один непустой `machine_uid` на устройство (partial unique constraint).

### 4.2 Материалы (основной контур сканера)

- **`MaterialKind`** — справочник типов материала (`code`, `name`, флаги вроде «литература»). Новые записи от сканера с неизвестным содержимым привязываются к виду с кодом **`generic`** (или к первому доступному виду, если `generic` отсутствует — см. защитный код в `upload_scan`).
- **`Material`** — логическая сущность файла в каталоге: `material_kind`, опционально `project`, `topic`, `file_name`, `extension`, `size_bytes`, `checksum_sha256`, `source_path`, описание, M2M **`tags`**. Флаги очереди разбора: **`scan_import_pending`**, **`scan_inbox_ignored`**.
- **`MaterialLocation`** — конкретное вхождение: **`material`**, **`device`**, **`storage_location`**, **`relative_path`** (POSIX-подобная строка относительно корня), `checksum`, `sync_status`, `availability` (present/missing), M2M теги на уровне пути.

Уникальность размещения: `(device, storage_location, relative_path)`.

**Дедупликация при приёме скана:** сначала поиск **`Material`** с тем же **`checksum_sha256`** и **`file_name`**, если checksum непустой; иначе создаётся новый материал с `scan_import_pending=True`.

### 4.3 Legacy-контур «файловых ресурсов»

- **`Project`**, **`Tag`**, **`FileResource`**, **`FileResourceLocation`** — используются существующим UI импорта/учёта. При загрузке скана сервер дополнительно пытается **сопоставить** записи скана с существующими `FileResource` (по SHA-256, затем по имени файла) и создаёт/обновляет **`FileResourceLocation`** — см. `_link_file_resources_from_scan_entry` в `catalog/api_views.py`.

### 4.4 Связанные сущности

- **`LinkedResource`** — ссылки URL/DOI/заметки, привязанные к `Material` (не путать с потоком сканера).

---

## 5. REST API (`/api/v1/`)

Маршруты объявлены в `catalog/api_urls.py`, реализация — `catalog/api_views.py`, сериализация — `catalog/api_serializers.py`.

### 5.1 Регистрация устройства

- **`POST /api/v1/devices/register/`**
- **Доступ:** без токена (`AllowAny`).
- Тело: данные из **`DeviceRegistrationSerializer`** (в т.ч. `machine_uid`, `hostname`, `os_name`, `platform_name`, опционально `display_name`).
- Поведение: найти `Device` по `machine_uid` или создать; при отсутствии **`scanner_token`** сгенерировать (`secrets.token_urlsafe`), сохранить.
- Ответ: `device_id`, **`scanner_token`**, `created`.

Агент сохраняет токен в локальной SQLite таблице **`scanner_state`** (ключ вроде `scanner_token`) через `ScannerCache.state_set`.

### 5.2 Загрузка результатов сканирования

- **`POST /api/v1/scans/upload/`**
- **Аутентификация:** заголовок **`Authorization: Scanner <scanner_token>`**.
- Реализация: **`ScannerTokenAuthentication`** (`catalog/authentication.py`) — разбор заголовка, поиск `Device` по токену, обёртка **`ScannerUser`** для DRF.
- Разрешение: кастомный **`IsScannerAgent`** — проверка, что `request.user` есть `ScannerUser`.

Тело запроса валидируется **`ScanUploadSerializer`**. Логически это пакет:

- `device_machine_uid` — должен совпадать с устройством токена (иначе 400);
- `storage_location_root` — строка корня;
- `entries` — список объектов **файлов/папок** (как в DTO на клиенте);
- `deleted_relative_paths` — пути, исчезнувшие с диска.

В транзакции для каждой записи с `availability == present` и `kind != folder` (папки в материалы не материализуются так же, как файлы — см. код отсечения):

1. Upsert **`StorageLocation`** для `(device, root_path)`.
2. Найти или создать **`Material`** (вид `generic`, флаги очереди разбора).
3. **`MaterialLocation.objects.update_or_create`** по `(device, storage_location, relative_path)`.
4. **`_link_file_resources_from_scan_entry`** — связь с legacy `FileResource` / `FileResourceLocation`.

Для **`deleted_relative_paths`** обновляются соответствующие **`MaterialLocation`** (отмечается отсутствие и т.п. — см. полный код в `api_views.py` после обработки `entries`).

Ошибка **500** «No MaterialKind» возможна, если в БД не выполнены миграции или не создан ни один `MaterialKind` — это защитный ранний выход при создании материала.

### 5.3 Прочие endpoint’ы

- **`POST /api/v1/heartbeat/`** — активность сканера (обновление полей устройства).
- **`GET /api/v1/status/`** — проверка живости (используется CLI `metastore-scanner status`).
- **`GET /api/v1/materials/`**, **`locations/`**, **`storage-locations/`** — выборки для агента/отладки (ограничения по объёму см. в коде).

---

## 6. Веб-интерфейс (Django views)

Основные URL см. `catalog/urls.py`. Для потока сканирования важны:

- **`/scan-inbox/`** (`ScanInboxView`) — список материалов с **`scan_import_pending=True`** и **`scan_inbox_ignored=False`**. POST: массовое назначение проекта/тегов, действия **`delete`** (удаление материала) и **`ignore`** (снять с очереди, выставить `scan_inbox_ignored=True` без удаления сущности).
- **`/how-to-scan/`** — статическая справка с командами CLI для пользователя.

Остальные представления — CRUD по проектам, устройствам, `FileResource`, материалам, тегам, поиск — классические CBV/View в `catalog/views.py`.

---

## 7. metastore-scanner: архитектура пакета

### 7.1 Точка входа и команды

Модуль **`scanner/cli.py`**:

- Парсинг **`argparse`**, подкоманды: `device-info`, `config`, `status`, `reset-cache`, **`scan`**, **`sync`**.
- **`scan`**:
  - загружает опционально **`scanner.yaml`** (`load_config`);
  - собирает **`find_patterns`** из YAML (`find_names`, `find_extensions`) и CLI (`--find`, **`--ext`**);
  - преобразование расширений: функция **`_extensions_to_find_patterns`** — токены вида `pdf`, `.pdf`, списки через запятую/пробел → шаблоны **`*.pdf`** (fnmatch по **basename**);
  - определяет **корни** обхода: `--path`, `--find-root`, либо из конфига `scan_paths` / `find_roots`;
  - строит **`ScanOptions`** и вызывает **`FilesystemScanner.scan_root`** для каждого корня;
  - формирует **`ScanBatch`** (только `present` записи в пакете отправки, плюс списки удалённых путей);
  - при наличии конфига: регистрация устройства **`_ensure_registered`**, постановка батчей в очередь и **`flush_queue`**; иначе сообщение о локальном только кэше.

Флаг **`--dry-run`** сериализует JSON батчей в stdout без отправки.

### 7.2 Конфигурация YAML (`scanner/config/loader.py`)

Класс **`ScannerConfig`** (dataclass) поля включают:

- `server_url`, `scan_paths`, `exclude_patterns`, `calculate_checksums`, `device_display_name`;
- **`known_paths_only`** — не обходить дерево, только пути из локальной БД;
- **`find_names`**, **`find_extensions`**, **`find_roots`**, **`find_discover_on_disk`**;
- **`prune_artifact_dirs`** — не спускаться в типичные служебные каталоги при полном обходе.

Файл по умолчанию: **`./scanner.yaml`** (текущая рабочая директория процесса).

### 7.3 Локальный кэш (`scanner/cache/db.py`)

SQLite-файл по умолчанию рядом с процессом (**`scanner.db`**, путь задаётся CLI `--db` или константы).

Таблицы:

- **`scanned_files`** / **`scanned_folders`** — последнее известное состояние для инкрементального скана (размер, `mtime_ns`, SHA-256);
- **`sync_queue`** — JSON-пэйлоады типа `scan_upload` со статусом pending/error;
- **`scanner_state`** — ключ-значение (в т.ч. токен).

Инкрементальная стратегия: при неизменных размере и времени модификации хеш можно не пересчитывать (если не задан **`full_rescan`** на CLI).

### 7.4 Обход файловой системы (`scanner/filesystem/scanner.py`)

Класс **`FilesystemScanner`**, опции — dataclass **`ScanOptions`**:

| Поле | Назначение |
|------|------------|
| `recursive` | рекурсивный обход |
| `calculate_checksums` | считать SHA-256 (или пропуск при `--no-checksum`) |
| `exclude_patterns` | fnmatch по имени или относительному пути |
| `mtime_after` / `mtime_before` | фильтр на отправку на сервер; обход дерева при этом остаётся полным |
| `known_paths_only` | только пути из кэша для данного корня |
| `find_name_patterns` | шаблоны `*.pdf` и т.д.; пусто = полный инвентарный режим (с учётом prune) |
| `find_discover_on_disk` | при ненулевых шаблонах: искать по диску под корнем; иначе фильтровать только записи из кэша |
| `prune_artifact_dirs` | при полном обходе не заходить в `__pycache__`, `.git`, `node_modules`, venv и др. (`os.walk` с фильтрацией `dirnames`) |

Дополнительно: предупреждения о **частых совпадениях basename** (`duplicate_basename_warn_threshold`), прогресс в stdout.

**Несовместимость:** `known_paths_only` и режим поиска по шаблонам (`--find` / `--ext` / YAML) взаимоисключаются — CLI выводит ошибку и код возврата 1.

### 7.5 Контрольные суммы (`scanner/checksum/engine.py`)

Потоковое чтение файла по блокам для **SHA-256** и опционально **MD5** (в текущих типичных настройках MD5 может не использоваться в пакете отправки).

### 7.6 Идентификация устройства (`scanner/device/detector.py`)

Формирование **`machine_uid`** и человекочитаемых полей ОС (различия Windows/Linux/macOS). Используется при регистрации и в полезной нагрузке батча.

### 7.7 DTO (`scanner/models/dto.py`)

- **`ScanEntry`** — одна запись обхода (файл или папка), сериализуется в JSON для API.
- **`ScanBatch`** — полный пакет для `upload_scan`: `device_machine_uid`, `storage_location_root`, `scanner_version`, `entries`, `deleted_relative_paths`.

### 7.8 HTTP-клиент и синхронизация

- **`scanner/api/client.py`** — обёртка над `requests`: базовый URL из конфига, заголовок **`Authorization`**, методы `register_device`, `upload_scan_results`, `get_server_status`, `send_heartbeat`, и т.д.
- **`scanner/sync/service.py`** — **`SyncService`**: `enqueue_batch`, **`flush_queue`** (последовательная отправка, при ошибке — пометка в очереди с текстом ошибки).

Команда **`sync`** отдельно вызывает только `flush_queue` — полезно при временной недоступности сервера после успешного локального скана.

---

## 8. Согласованность данных и типичные сценарии

1. **Первый запуск агента:** нет токена → `POST register` → сохранение токена → `scan` ставит батчи в очередь → отправка → heartbeat.
2. **Офлайн:** `scan` записал в `sync_queue` → позже `sync` или повторный `scan` с **`flush_queue`**.
3. **Только локальный учёт:** удалить или не создавать `scanner.yaml` — скан обновит SQLite, но не отправит (сообщение в консоли).
4. **Фильтр по расширениям:** CLI **`--ext`** и YAML **`find_extensions`** сводятся к тем же **`find_name_patterns`**, что и **`--find "*.pdf"`** — единый код в **`FilesystemScanner`**.

---

## 9. Точки расширения и сопровождение

- Новые поля в payload скана: расширить **`ScanEntry`** / сериализатор **`ScanUploadSerializer`** и миграцию моделей на сервере при необходимости сохранения.
- Новые режимы фильтрации на клиенте: расширять **`ScanOptions`** и ветвления в **`FilesystemScanner.scan_root`** (осторожно с производительностью на больших деревьях).
- Ужесточение безопасности веб-UI: middleware аутентификации, отключение публичного `register` или rate limiting на уровне reverse proxy.

---

## 10. Версионирование и тестирование

Версия пакета сканера участвует в поле **`scanner_version`** батча (`scanner/__version__`).

После изменений моделей сервера:

```bash
python manage.py makemigrations
python manage.py migrate
```

Проверка синтаксиса агента:

```bash
py -m compileall -q metastore-scanner/scanner
```

---

*Документ отражает состояние кодовой базы на момент составления: при расхождениях приоритет у фактического кода в репозитории.*
