#!/bin/sh

# Fail fast
set -e

# --- Функция для проверки готовности БД ---
wait_for_db() {
    echo "-> (Entrypoint) Ожидание запуска PostgreSQL..."
    python << END
import os
import psycopg
import sys
import time

try:
    # Безопасно формируем строку подключения, которая корректно экранирует спецсимволы
    conn_str = psycopg.conninfo.make_conninfo(
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
            connection = psycopg.connect(conn_str, connect_timeout=2)
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

# Ждем БД
wait_for_db

# Указываем пользователя и группу, под которыми будет работать приложение
APP_USER=kronon
APP_GROUP=kronon

# Устанавливаем права на папки (медиа, статика, логи)
# Это позволяет монтировать volumes локально без проблем с правами
echo "-> (Entrypoint) Настройка прав доступа..."
chown -R "${APP_USER}:${APP_GROUP}" /app/media /app/staticfiles /app/logs

# Выполняем миграции (если нужно)
if [ "${APPLY_MIGRATIONS:-false}" = "true" ]; then
    echo "-> (Entrypoint) Применение миграций..."
    # Запускаем от имени kronon
    su-exec "${APP_USER}" python manage.py migrate --noinput
fi

# Собираем статику
if [ "${COLLECT_STATIC:-false}" = "true" ]; then
    echo "-> (Entrypoint) Сбор статики..."
    su-exec "${APP_USER}" python manage.py collectstatic --noinput
fi

# Анализируем команду, чтобы понять, что будет запущено
case "$@" in
    # Запуск веб-сервера (Gunicorn + Uvicorn Workers для Ninja/Async)
    *"gunicorn"*)
        echo "-> (Entrypoint web) Запуск Django (Gunicorn + Uvicorn)..."
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
        echo "-> (Entrypoint: Celery) Запуск Celery Worker..."
        exec su-exec "${APP_USER}" "$@"
        ;;

    # Запуск Celery Beat
    *"celery"*"beat"*)
        echo "-> (Entrypoint: Celery) Запуск Celery Beat..."
        # Удаляем pid файл, если он остался от прошлого запуска
        rm -f celerybeat.pid
        exec su-exec "${APP_USER}" "$@"
        ;;

    # Любая другая команда
    *)
        echo "-> (Entrypoint) Запуск переданной команды: $@"
        exec su-exec "${APP_USER}" "$@"
        ;;
esac
