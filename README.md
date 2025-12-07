# MetaStore

В репозитории находится Django-приложение для каталогизации метаданных файловых ресурсов.

## Как прямо сейчас получить архив с кодом
Если нужен готовый ZIP, он уже лежит в проекте. Скопируйте его в удобное место и скачайте через интерфейс, с которым работаете:
1. Перейдите в корень проекта (если ещё не там):
   ```bash
   cd /workspace/MetaStore
   ```
2. Скопируйте готовый архив наверх (пример — в `/workspace`, откуда обычно можно скачать файл):
   ```bash
   cp archives/metastore.zip /workspace/metastore.zip
   ```
3. Скачайте файл `/workspace/metastore.zip` через ваш инструмент (VS Code, SFTP или «Download» в веб-интерфейсе). Если нужен другой путь, замените `/workspace/metastore.zip` на свой.

Ниже — дополнительные сведения про проект и работу с git.

Если в терминале видите сообщение `nothing to commit, working tree clean`, это значит, что в рабочей копии нет новых изменений — код уже сохранён в git в текущей ветке.

## Структура
- `manage.py` — точка входа Django.
- `metastore/` — настройки проекта.
- `catalog/` — приложение с моделями проектов, устройств, файловых ресурсов, тегов, CRUD-представлениями, поиском и командой импорта CSV.

## Как понять, что код есть и в какой ветке
- Посмотреть файлы локально:
  ```bash
  ls
  ```
- Список основных директорий должен включать `catalog`, `metastore`, `manage.py` и папку `archives` с zip-архивом.
- Посмотреть историю коммитов:
  ```bash
  git log --oneline --decorate -5
  ```
- Узнать текущую ветку (по умолчанию сейчас `work`):
  ```bash
  git branch -vv
  ```

## Как быстро закоммитить изменение
1. Посмотрите, какие файлы поменялись:
   ```bash
   git status
   ```
2. Добавьте нужные файлы в индекс (пример — все изменения сразу):
   ```bash
   git add .
   ```
3. Создайте коммит с понятным сообщением:
   ```bash
   git commit -m "Короткое описание изменений"
   ```
4. Отправьте коммит на GitHub (если origin уже настроен):
   ```bash
   git push
   ```
   Если origin ещё не привязан, смотрите раздел выше «Как получить код на GitHub».

## Как получить код на GitHub
> Важный момент: сейчас удалённый `origin` не настроен, поэтому на GitHub ничего не отправлялось. Нужно один раз привязать удалённый репозиторий.

1. Создайте пустой репозиторий в вашем аккаунте GitHub (например, `MetaStore`).
2. В корне проекта привяжите его как origin и запушьте текущую ветку `work` или переименуйте её в `main`:
   ```bash
   git remote add origin https://github.com/<user>/<repo>.git
   # вариант 1: оставить ветку work
   git push -u origin work
   # вариант 2: сделать основной веткой main
   git branch -M main
   git push -u origin main
   ```
3. После этого код появится на GitHub. Новые изменения отправляйте обычным `git push`.

## Как склонировать или скопировать локально
- Клонировать на другой диск/машину:
  ```bash
  git clone https://github.com/<user>/<repo>.git
  ```
- Сделать локальный архив без GitHub:
  ```bash
  cd /workspace
  tar -czf MetaStore.tar.gz MetaStore
  ```
- Готовый ZIP-архив текущего состояния (создан командой `git archive`) лежит в `archives/metastore.zip` в корне проекта. Его можно
  скачать или отправить вручную, если GitHub недоступен.

### Как скачать готовый ZIP-архив из терминала
1. Перейдите в корень проекта:
   ```bash
   cd /workspace/MetaStore
   ```
2. Убедитесь, что файл на месте:
   ```bash
   ls archives
   # должен быть metastore.zip
   ```
3. Скопируйте архив туда, откуда удобно забрать (например, в `/workspace`):
   ```bash
   cp archives/metastore.zip /workspace/metastore.zip
   ```
   После этого можете скачать файл `/workspace/metastore.zip` через используемый вами интерфейс (VS Code, SFTP, File → Download и
   т.п.). Если нужен другой путь, просто замените `/workspace/metastore.zip` на нужный.

## Минимальный запуск локально
1. Создайте и активируйте виртуальное окружение Python 3.10.
2. Установите зависимости (Django LTS и psycopg2-binary):
   ```bash
   pip install "Django>=4.2,<5.0" psycopg2-binary
   ```
3. Настройте переменные окружения для подключения к PostgreSQL (см. `metastore/settings.py`).
4. Выполните миграции и запустите сервер:
   ```bash
   python manage.py migrate
   python manage.py runserver
   ```

## Импорт метаданных из CSV
Пример запуска команды импорта (файл с колонками `project_name,device_name,device_type,relative_path,file_name,extension,size_bytes,created_at_fs,updated_at_fs,checksum,tags`):
```bash
python manage.py import_metadata path/to/metadata.csv
```
Команда создаст недостающие проекты, устройства, теги и обновит/добавит записи `FileResource`.

## Как запустить сервер «прямо сейчас»
1. Убедитесь, что PostgreSQL запущен и у вас есть база с пользователем и паролем.
2. Экспортируйте переменные окружения (пример для базы `metastore`):
   ```bash
   export DB_NAME=metastore
   export DB_USER=postgres
   export DB_PASSWORD=postgres
   export DB_HOST=127.0.0.1
   export DB_PORT=5432
   ```
3. Примените миграции и поднимите сервер разработки:
   ```bash
   python manage.py migrate
   python manage.py runserver 0.0.0.0:8000
   ```
4. Перейдите в браузере по адресу `http://localhost:8000/`.
5. Чтобы зайти в админку, создайте суперпользователя и зайдите на `/admin/`:
   ```bash
   python manage.py createsuperuser
   ```

## Что делать дальше
1. Вносите изменения в код или шаблоны.
2. Добавьте их в git и создайте коммит:
   ```bash
   git add .
   git commit -m "Ваш комментарий"
   ```
3. Отправьте коммит в GitHub:
   ```bash
   git push
   ```
Если после `git add .` и `git commit ...` выводится `nothing to commit`, значит изменения не найдены — продолжайте работу или убедитесь, что редактировали файлы в этом репозитории.

