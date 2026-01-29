# ==================================================================================
# 1. Builder: Сборка зависимостей и утилит
# ==================================================================================
FROM python:3.12-slim-bookworm AS builder

# Устанавливаем переменные окружения для Poetry
ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Устанавливаем системные зависимости для сборки
# - build-essential, wget, ca-certificates: для компиляции su-exec
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Компилируем su-exec (статический бинарник)
RUN wget -O su-exec.tar.gz https://github.com/ncopa/su-exec/archive/master.tar.gz && \
    tar -xzf su-exec.tar.gz && \
    cd su-exec-master && \
    make && \
    cp su-exec /usr/local/bin/su-exec && \
    cd / && \
    rm -rf su-exec.tar.gz su-exec-master

# Устанавливаем Poetry
RUN pip install --upgrade pip && pip install poetry

# Копируем файлы зависимостей
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости (без dev)
RUN poetry install --only main --no-root


# ==================================================================================
# 2. Final: Финальный образ
# ==================================================================================
FROM python:3.12-slim-bookworm AS final

# Окружение
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VIRTUAL_ENV=/app/.venv \
    PYTHONPATH="/app" \
    PATH="/app/.venv/bin:$PATH" \
    # Указываем Django, где искать настройки
    DJANGO_SETTINGS_MODULE="config.settings"

WORKDIR /app

# Устанавливаем Runtime зависимости
# - libpq-dev: для работы драйвера psycopg
# - curl: для healthcheck
# - gettext: для i18n (компиляция переводов .mo)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-dev \
    curl \
    gettext \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя и группу для запуска от non-root
RUN groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser

# Копируем артефакты из builder
COPY --from=builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=builder /app/.venv /app/.venv

# Копируем Entrypoint и устанавливаем ему права на выполнение
COPY ./docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Копируем весь проект
COPY . .

# Создаем папки для статики, медиа и логов
RUN mkdir -p /app/staticfiles /app/media /app/logs

# Собираем статику (Whitenoise)
# SECRET_KEY заглушка нужна, так как settings импортируется при collectstatic
RUN SECRET_KEY=build_mode_key \
    DATABASE_URL=postgres://none \
    python manage.py collectstatic --noinput

# Отдаем права пользователю
RUN chown -R appuser:appgroup /app/staticfiles /app/media /app/logs

# Сообщаем Docker, что контейнер будет слушать порт 8000
EXPOSE 8000

# Устанавливаем скрипт как точку входа (он будет выполнен перед основной командой контейнера)
ENTRYPOINT ["/entrypoint.sh"]

# Команда по умолчанию (для самодостаточности контейнера)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
