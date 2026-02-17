# ==============================================================================
# 1. BUILDER: Сборка зависимостей и утилит
# ==============================================================================
FROM python:3.14-slim-bookworm AS builder

# Устанавливаем переменные окружения для Poetry
ENV POETRY_VERSION=2.2.0 \
    POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_VIRTUALENVS_IN_PROJECT=false \
    POETRY_VIRTUALENVS_PATH="/opt/venv" \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Устанавливаем системных зависимостей для сборки
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Компилируем su-exec (для безопасного переключения пользователя)
RUN wget -O su-exec.tar.gz https://github.com/ncopa/su-exec/archive/master.tar.gz && \
    tar -xzf su-exec.tar.gz && \
    cd su-exec-master && \
    make && \
    cp su-exec /usr/local/bin/su-exec && \
    cd / && \
    rm -rf su-exec.tar.gz su-exec-master

# Обновляем pip и устанавливаем Poetry
RUN pip install --upgrade pip && pip install "poetry==$POETRY_VERSION"

# Копируем файлы зависимостей
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости (Production only)
RUN poetry install --only main --no-root

# Создаем стабильную символическую ссылку на venv (убираем хеш из пути)
RUN ln -s /opt/venv/$(ls /opt/venv | head -n 1) /opt/venv/active

# ==============================================================================
# 2. RUNNER: Финальный образ
# ==============================================================================
FROM python:3.14-slim-bookworm AS runner

# Переменные окружения для Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH="/app" \
    HOME="/home/kronon" \
    XDG_CACHE_HOME="/home/kronon/.cache" \
    VIRTUAL_ENV="/opt/venv/active" \
    PATH="/opt/venv/active/bin:$PATH"


WORKDIR /app

# Устанавливаем runtime-зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq5 \
    gettext \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем группу kronon (GID 1000) и non-root пользователя kronon (UID 1000)
RUN groupadd -g 1000 kronon && \
    useradd -u 1000 -g kronon -s /bin/sh -m kronon

# Копируем скомпилированные артефакты и venv из билдера
COPY --from=builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=builder /opt/venv /opt/venv

# Копируем энтрипойнт и устанавливаем права
COPY --chmod=755 docker/entrypoint.sh /entrypoint.sh

# Копируем код проекта
COPY --chown=kronon:kronon . .

# Создаем папки для статики, медиа и логов (чтобы у kronon были права)
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R kronon:kronon /app/staticfiles /app/media /app/logs

EXPOSE 8000

# Точка входа
ENTRYPOINT ["/entrypoint.sh"]

# Команда по умолчанию
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--worker-class", "uvicorn.workers.UvicornWorker"]
