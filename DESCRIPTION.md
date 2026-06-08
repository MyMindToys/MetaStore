# MetaStore — архитектура и компоненты

Распределённый **каталог метаданных**: сервер **не хранит файлы**, только сведения о том, на каком устройстве и по какому пути объект находится, его размере, контрольной сумме и статусе синхронизации.

Система состоит из двух частей:

| Компонент | Роль |
|-----------|------|
| **metastore-server** (этот репозиторий, Django) | Центральное хранилище метаданных, поиск, веб-интерфейс, REST API, админка |
| **metastore-scanner** (`metastore-scanner/`) | Локальный CLI-агент: обход ФС, checksum, локальный SQLite-кэш, очередь синхронизации, вызовы API |

Поток данных: **Scanner → REST API → Django → PostgreSQL** (или SQLite в режиме разработки).

---

## metastore-server (Django)

### Стек

- Python 3.x, **Django 4.2 LTS**, **Django REST Framework**
- БД: **PostgreSQL** (`POSTGRES_*` в окружении) или **SQLite** при `USE_SQLITE=1`
- Веб: шаблоны + Bootstrap 5 (существующий UI каталога)

### Конфигурация окружения

См. `metastore/settings.py`:

- `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`
- `USE_SQLITE` — переключение на файл `db.sqlite3`
- PostgreSQL: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`

### Модели домена

**Legacy (ручной каталог):** `Project`, `Device`, `Tag`, `FileResource` — сохранены для текущего CRUD UI.

**Расширение устройства (`Device`):**

- `machine_uid`, `hostname`, `os_name`, `platform_name`
- `last_seen_at`, `last_sync_at`
- `scanner_token` — секрет агента после регистрации (уникальный)

**Новый каталог материалов (источник истины для scanner/API):**

- **`StorageLocation`** — корень сканирования на устройстве (`device`, `root_path`, имя).
- **`Material`** — логический объект файла (`file_name`, `extension`, `size_bytes`, `checksum_sha256`, опционально `project`, теги).
- **`MaterialLocation`** — размещение: `device`, `storage_location`, `relative_path`, `checksum`, `sync_status`, `availability` (present/missing).

Дедупликация материалов при приёме скана: по `checksum_sha256` + `file_name`, если checksum задан.

### REST API (`/api/v1/`)

Аутентификация агента: заголовок **`Authorization: Scanner <scanner_token>`** (выдаётся при регистрации).

| Метод | Путь | Доступ | Назначение |
|-------|------|--------|------------|
| POST | `/api/v1/devices/register/` | публичный | Регистрация по `machine_uid`, возврат `scanner_token` |
| POST | `/api/v1/scans/upload/` | Scanner | Пакет результатов сканирования (JSON) |
| POST | `/api/v1/heartbeat/` | Scanner | Обновление `last_seen_at` |
| GET | `/api/v1/status/` | публичный | Проверка живости сервиса |
| GET | `/api/v1/materials/` | Scanner | Список материалов (ограничение выборки) |
| GET | `/api/v1/locations/` | Scanner | Размещения материалов |
| GET | `/api/v1/storage-locations/` | Scanner | Зарегистрированные корни сканирования |

Реализация: `catalog/api_views.py`, `catalog/api_urls.py`, `catalog/authentication.py`, `catalog/api_serializers.py`.

### Ответственность сервера

- Хранение каталога, связей, поиск по существующему UI (legacy-модели).
- Приём метаданных от сканеров, обновление **Material** / **MaterialLocation**, пометка отсутствующих путей по списку `deleted_relative_paths`.
- **Не выполняет** сканирование локальных дисков сервера и не считает checksum файлов на сервере.

---

## metastore-scanner (CLI)

Расположение: каталог **`metastore-scanner/`** (отдельный пакет, без Django ORM).

### Зависимости

- Обязательные: `requests`
- Для YAML-конфига: `PyYAML` (см. `requirements.txt`)

Установка в режиме разработки:

```bash
cd metastore-scanner
pip install -r requirements.txt
pip install -e .
```

### Модули

| Пакет | Назначение |
|-------|------------|
| `scanner/device/detector.py` | `machine_uid`: Linux `/etc/machine-id`, Windows MachineGuid (реестр), macOS `ioreg` UUID при наличии, иначе стабильный fallback |
| `scanner/cache/db.py` | SQLite `scanner.db`: файлы/папки кэша, очередь `sync_queue`, ключ-значение `scanner_state` (токен) |
| `scanner/filesystem/scanner.py` | Рекурсивный обход через `pathlib`, incremental checksum (mtime/size), обнаружение удалений |
| `scanner/checksum/engine.py` | SHA256 / MD5 потоково по chunk |
| `scanner/config/loader.py` | YAML-конфигурация (`scanner.yaml`) |
| `scanner/api/client.py` | HTTP-клиент с timeout и urllib3 retry |
| `scanner/sync/service.py` | Очередь офлайн-синхронизации |
| `scanner/cli.py` | Команды CLI |

### Команды

```text
metastore-scanner device-info
metastore-scanner scan [--path DIR] [--config scanner.yaml] [--dry-run] [--full-rescan] [--no-checksum]
metastore-scanner sync
metastore-scanner status
metastore-scanner config --path scanner.yaml
metastore-scanner reset-cache
```

Пример конфига: `scanner.example.yaml`.

### Офлайн-first

Результаты скана при наличии `scanner.yaml` ставятся в **`sync_queue`**; команда **`sync`** повторно отправляет накопленное. Токен сохраняется в **`scanner_state`** после регистрации.

### Сборка standalone

Скрипт-заготовка: `metastore-scanner/scripts/build_pyinstaller.ps1` (требуется PyInstaller).

---

## Обновление документации и миграций

После изменения моделей сервера:

```bash
python manage.py makemigrations
python manage.py migrate
```

---

*Версия документа соответствует введению двухкомпонентной архитектуры (server + scanner) и API `/api/v1/`.*
