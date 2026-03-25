"""
Команда восстановления зависимостей миграций после их полной очистки.

Аргумент `--hide` прячет (переименовывает) файл миграции создания системного пользователя,
чтобы Django не падал из-за, существующей в этом файле, зависимости.

Аргумент `--repair` восстанавливает (переименовывает) файл миграции создания системного пользователя
и запускает методы `fix_users_migrations` и `add_trigram_dependencies`.

Метод `fix_users_migrations` добавляет зависимость на ('users', '0001_initial')
в миграцию создания системного пользователя (apps/users/migrations/0002_create_system_user.py).

Метод `add_trigram_dependencies` добавляет зависимость на ('common', '0001_install_trigram')
во все 0001_initial.py миграции, где используется GIN/Trigram.
"""

import re
from pathlib import Path
from typing import Any

from django.core.management import CommandParser
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Управляет кастомными миграциями при пересоздании базы"

    # --- Конфигурация для триграмм ---
    TRIGRAM_DEPENDENCY = "('common', '0001_install_trigram')"
    APPS_WITH_GIN = ["clients"]  # Приложения, где есть GinIndex

    # --- Конфигурация для системного пользователя ---
    USERS_APP = "users"
    SYSTEM_USER_MIGRATION = "0002_create_system_user.py"
    # Пути к файлу миграции создания системного пользователя и его временной копии
    SYSTEM_USER_MIGRATION_PATH = Path(f"apps/{USERS_APP}/migrations/{SYSTEM_USER_MIGRATION}")
    SYSTEM_USER_MIGRATION_BACKUP_PATH = Path(f"apps/{USERS_APP}/migrations/{SYSTEM_USER_MIGRATION}.bak")

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument(
            "--hide",
            action="store_true",
            help="Спрятать кастомные миграции перед makemigrations",
        )
        parser.add_argument(
            "--repair",
            action="store_true",
            help="Вернуть кастомные миграции и починить связи",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if options["hide"]:
            # Прячем кастомные миграции
            self.hide_custom_migrations()
        elif options["repair"]:
            # Восстанавливаем кастомные миграции
            self.restore_custom_migrations()
            # Привязываем 0002_create_system_user к 0001_initial
            self.fix_users_migrations()
            # Привязываем 0001_initial других приложений к 0001_install_trigram
            self.add_trigram_dependencies()

    def hide_custom_migrations(self) -> None:
        """
        'Прячет' файлы кастомных миграции.
        (Переименовывает *.py в *.py.bak)
        """
        if self.SYSTEM_USER_MIGRATION_PATH.exists():
            self.SYSTEM_USER_MIGRATION_PATH.rename(self.SYSTEM_USER_MIGRATION_BACKUP_PATH)
            self.stdout.write(self.style.WARNING(f"[-] {self.SYSTEM_USER_MIGRATION} спрятан во временный файл .bak"))

    def restore_custom_migrations(self) -> None:
        """
        'Возвращает' файлы кастомных миграции, если они были спрятаны.
        (Переименовывает *.py.bak в *.py)
        """
        if self.SYSTEM_USER_MIGRATION_BACKUP_PATH.exists():
            self.SYSTEM_USER_MIGRATION_BACKUP_PATH.rename(self.SYSTEM_USER_MIGRATION_PATH)
            self.stdout.write(self.style.SUCCESS(f"[+] {self.SYSTEM_USER_MIGRATION} возвращен на место"))

        if not self.SYSTEM_USER_MIGRATION_PATH.exists():
            self.stdout.write(self.style.ERROR(f"❌ Файл {self.SYSTEM_USER_MIGRATION} не найден!"))

    def fix_users_migrations(self) -> None:
        """Привязывает 0002_create_system_user к 0001_initial."""
        content = self.SYSTEM_USER_MIGRATION_PATH.read_text(encoding="utf-8")

        # Заменяем [] на  [("users", "0001_initial"),]
        pattern = r"dependencies\s*=\s*\[.*?\]"
        replacement = f"dependencies = [('{self.USERS_APP}', '0001_initial'),]"
        new_content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        self.SYSTEM_USER_MIGRATION_PATH.write_text(new_content, encoding="utf-8")
        self.stdout.write(self.style.SUCCESS(f"[+] {self.SYSTEM_USER_MIGRATION}: привязан к 0001_initial"))

    def add_trigram_dependencies(self) -> None:
        """Добавляет зависимость на ('common', '0001_install_trigram') в 0001_initial указанных приложений."""

        for app in self.APPS_WITH_GIN:
            migration_path = Path(f"apps/{app}/migrations/0001_initial.py")

            if not migration_path.exists():
                self.stdout.write(f"[-] {migration_path}: Файл initial-миграции не найден, пропущено")
                continue

            content = migration_path.read_text(encoding="utf-8")

            if self.TRIGRAM_DEPENDENCY in content:
                self.stdout.write(f"[.] {migration_path}: триграммы уже в зависимостях")
                continue

            # Вставляем зависимость
            pattern = r"(dependencies\s*=\s*\[)"
            replacement = f"\\1\n        {self.TRIGRAM_DEPENDENCY},"
            new_content = re.sub(pattern, replacement, content)
            migration_path.write_text(new_content, encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"[+] {migration_path}: добавлена зависимость от триграмм"))
