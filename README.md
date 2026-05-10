# MetaStore

Центральный **каталог метаданных** файлов на множестве устройств: сервер хранит только описания и связи; **файлы не загружаются**. Сканирование дисков выполняется отдельным CLI-агентом **`metastore-scanner`**.

## Компоненты

| Проект | Описание |
|--------|----------|
| **Корень репозитория** | Django-приложение (`catalog`), REST API `/api/v1/`, админка, веб-каталог |
| **`metastore-scanner/`** | Локальный Python CLI: обход ФС, checksum, SQLite-кэш, синхронизация с сервером |

Подробная архитектура (краткий обзор): **[DESCRIPTION.md](DESCRIPTION.md)**.

- **[TECHNICAL_ARCHITECTURE.md](TECHNICAL_ARCHITECTURE.md)** — полное техническое описание (архитектура, модули, API, потоки данных).
- **[USER_GUIDE.md](USER_GUIDE.md)** — руководство пользователя (сайт, сканер, типичные сценарии).

## Сервер: быстрый старт

```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
```

Задайте PostgreSQL или локальный режим:

```powershell
$env:USE_SQLITE = "1"
python manage.py migrate
python manage.py runserver
```

Переменные БД для Postgres: `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT` (см. `metastore/settings.py`).

Суперпользователь для `/admin/`:

```bash
python manage.py createsuperuser
```

## Scanner: быстрый старт

```bash
cd metastore-scanner
pip install -r requirements.txt
pip install -e .
copy scanner.example.yaml scanner.yaml
# отредактируйте server_url и scan_paths
metastore-scanner device-info
metastore-scanner scan --path "C:\path\to\folder"
```

При первом скане с валидным `scanner.yaml` выполняется регистрация устройства на сервере; токен сохраняется локально в SQLite (`scanner.db`).

**Полная справка по ключам CLI и полям `scanner.yaml`:** [metastore-scanner/README.md](metastore-scanner/README.md) (разделы «Как запускать», «Команда scan», таблицы флагов и примеры).

## API для агентов

- Регистрация: `POST /api/v1/devices/register/` (без токена).
- Остальные операции сканера: заголовок `Authorization: Scanner <scanner_token>`.

Детали контрактов — в **DESCRIPTION.md**.

## Лицензия и версии

Зависимости перечислены в `requirements.txt` (сервер) и `metastore-scanner/requirements.txt` (агент).
