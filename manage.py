#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
import uuid

from loguru import logger

# Используем pghistory для трекинга контекста консольных команд
from pghistory import context as pghistory_context
from sentry_sdk import set_context, set_tag


def main() -> None:
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # --- PGHISTORY CONTEXT INSTRUMENTATION ---

    # Игнорируем runserver (слишком много шума), миграции (конфликты схем) и тесты
    if (
        len(sys.argv) > 1
        and not sys.argv[1].startswith("runserver")
        and sys.argv[1] not in ["migrate", "makemigrations", "test"]
    ):
        # Генерируем correlation_id
        correlation_id = str(uuid.uuid7())

        command: str = " ".join(sys.argv[1:])

        # Данные для Sentry: приклеятся ко всем ошибкам, возникшим в рамках CLI-сессии
        set_tag("correlation_id", correlation_id)
        set_tag("service", "CLI")
        set_context("cli_command", {"full_command": command})

        # Оборачиваем в контекст Loguru (для красивых логов)
        with logger.contextualize(correlation_id=correlation_id):
            # Оборачиваем в контекст pghistory (для записей в БД)
            with pghistory_context(correlation_id=correlation_id, service="CLI", cli_command=command):
                execute_from_command_line(sys.argv)
    else:
        execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
