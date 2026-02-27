#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""

import os
import sys
from contextlib import ExitStack

# Используем pghistory для трекинга контекста консольных команд
from pghistory import context as pghistory_context


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

    # Явная типизация для mypy
    history_context: pghistory_context | ExitStack[bool | None]

    if (
        len(sys.argv) > 1
        and not sys.argv[1].startswith("runserver")
        and sys.argv[1] not in ["migrate", "makemigrations", "test"]
    ):
        # Оборачиваем выполнение команды в контекст
        # В БД в поле pgh_context будет: {"app_source": "CLI", "command": "..."}
        history_context = pghistory_context(app_source="CLI", command=" ".join(sys.argv[1:]))
    else:
        # Пустой контекстный менеджер, если трекинг не нужен
        history_context = ExitStack()

    with history_context:
        execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
