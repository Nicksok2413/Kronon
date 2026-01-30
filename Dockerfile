# ==============================================================================
# 1. BUILDER: Сборка зависимостей и утилит
# ==============================================================================
FROM python:3.12-slim-bookworm AS builder

# Устанавливаем переменные окружения для Poetry
ENV POETRY_VERSION=2.2.0 \
    POETRY_HOME="/opt/poetry" \
    POETRY_VIRTUALENVS_CREATE=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1 \
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

# Устанавливаем Poetry
RUN pip install "poetry==$POETRY_VERSION"

# Копируем файлы зависимостей
COPY pyproject.toml poetry.lock ./

# Устанавливаем зависимости (Production only)
RUN poetry install --only main --no-root


# ==============================================================================
# 2. RUNNER: Финальный образ
# ==============================================================================
FROM python:3.12-slim-bookworm AS runner

# Переменные окружения для Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Устанавливаем runtime-зависимостей
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq-5 \
    gettext \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Создаем группу kronon (GID 1000) и пользователя kronon (UID 1000)
# Для безопасности, чтобы не запускать приложение от root
# Для решения проблем с правами доступа к volumes
RUN groupadd -g 1000 kronon && \
    useradd -u 1000 -g kronon -s /bin/sh -m kronon

# Копируем артефакты из builder
COPY --from=builder /usr/local/bin/su-exec /usr/local/bin/su-exec
COPY --from=builder /app/.venv /app/.venv

# Копируем Entrypoint
COPY --chmod=755 scripts/entrypoint.sh /entrypoint.sh

# Копируем всё, так как у нас монолит
COPY --chown=kronon:kronon . .

# Создаем папки для статики и медиа (чтобы у kronon были права)
RUN mkdir -p /app/staticfiles /app/media /app/logs && \
    chown -R kronon:kronon /app/staticfiles /app/media /app/logs

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
