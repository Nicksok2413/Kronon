#!/bin/sh

# Выход при ошибке (fail fast)
set -e

# --- Функция для проверки готовности БД ---
wait_for_db() {
    echo "-> (Entrypoint) Ожидание запуска PostgreSQL..."
    /app/.venv/bin/python << END
import os
import psycopg
import sys
import time

try:
    # Безопасно формируем строку подключения, которая корректно экранирует спецсимволы
    conn_info = psycopg.conninfo.make_conninfo(
        dbname=os.environ.get("DB_NAME"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        host=os.environ.get("DB_HOST"),
        port=os.environ.get("DB_PORT"),
    )

    connection = None
    print("Попытка подключения к БД...")

    for attempt in range(30):
        try:
            connection = psycopg.connect(conn_info, connect_timeout=2)
            print(f"   Попытка {attempt+1}/30: PostgreSQL запущен - соединение установлено.")
            break
        except psycopg.OperationalError as exc:
            print(f"   Попытка {attempt+1}/30: PostgreSQL недоступен, ожидание... ({exc})")
            time.sleep(1)

    if connection is None:
        print("-> (Entrypoint) Не удалось подключиться к PostgreSQL после 30 секунд.")
        sys.exit(1)

    connection.close()

except KeyError as exc:
    print(f"-> (Entrypoint) Ошибка: переменная окружения {exc} не установлена.")
    sys.exit(1)
except Exception as exc:
    print(f"-> (Entrypoint) Произошла ошибка при проверке БД (psycopg3): {exc}")
    sys.exit(1)
END
}

# Указываем пользователя и группу, под которыми будет работать приложение
APP_USER=appuser
APP_GROUP=appgroup

# Устанавливаем права на логи и медиа
LOG_DIR="/app/logs"
MEDIA_DIR="/app/media"

# Проверка владельца через stat (быстрее, чем chown)
if [ -d "${LOG_DIR}" ]; then
    if [ "$(stat -c %U "${LOG_DIR}")" != "${APP_USER}" ]; then
        echo "-> (Entrypoint) Выдача прав на $LOG_DIR..."
        chown -R "${APP_USER}:${APP_GROUP} ${LOG_DIR}"
    fi
fi

if [ -d "${MEDIA_DIR}" ]; then
    if [ "$(stat -c %U "${MEDIA_DIR}")" != "${APP_USER}" ]; then
        echo "-> (Entrypoint) Выдача прав на $MEDIA_DIR..."
        chown -R "${APP_USER}:${APP_GROUP} ${MEDIA_DIR}"
    fi
fi

# Ожидание БД (только если команда требует БД)
case "$@" in
    *"gunicorn"*|*"uvicorn"*|*"manage.py"*|*"celery"*)
        wait_for_db
        ;;
esac

# Анализируем команду, чтобы понять, что будет запущено
case "$@" in
    # Запуск веб-сервера (Gunicorn + Uvicorn Workers для Ninja/Async)
    *"gunicorn"*)
        echo "-> Запуск Django (Gunicorn + Uvicorn)..."
        # Передаем управление su-exec, добавляя класс воркера uvicorn
        exec su-exec "${APP_USER}" gunicorn config.wsgi:application \
             --bind 0.0.0.0:8000 \
             --workers 3 \
             --worker-class uvicorn.workers.UvicornWorker \
             --access-logfile - \
             --error-logfile -
        ;;

    # Запуск Celery Worker
    *"celery"*"worker"*)
        echo "-> Запуск Celery Worker..."
        exec su-exec "${APP_USER}" celery -A config worker -l info
        ;;

    # Запуск Celery Beat
    *"celery"*"beat"*)
        echo "-> Запуск Celery Beat..."
        # Удаляем pid файл, если он остался от прошлого запуска
        rm -f celerybeat.pid
        exec su-exec "${APP_USER}" celery -A config beat -l info
        ;;

    # Любая другая команда (например, миграции)
    *)
        echo "-> Запуск переданной команды: $@"
        exec su-exec "${APP_USER}" "$@"
        ;;
esac
