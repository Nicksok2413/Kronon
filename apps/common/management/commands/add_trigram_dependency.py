"""
Команда добавляет зависимость на ('common', '0001_install_trigram')
во все 0001_initial.py или 0001_auto_*.py миграции, где используется GIN/Trigram.
"""

import pathlib
from typing import Any

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Добавляет зависимость на ('common', '0001_install_trigram') во все 0001_initial.py или 0001_auto_*.py миграции, где используется GIN/Trigram"

    DEPENDENCY = "('common', '0001_install_trigram')"
    MIGRATION_PATTERN = "0001*.py"

    # Приложения, где есть GinIndex
    APPS_WITH_GIN = ["clients"]

    def handle(self, *args: Any, **options: Any) -> None:

        for app in self.APPS_WITH_GIN:
            migrations_path = pathlib.Path(f"apps/{app}/migrations")

            if not migrations_path.exists():
                self.stdout.write(f"-> Папка миграций не найдена для приложения {app}, пропущено")
                continue

            # Ищем 0001_initial.py или 0001_auto_*.py
            for migration_file in migrations_path.glob(self.MIGRATION_PATTERN):
                content = migration_file.read_text()

                if self.DEPENDENCY in content:
                    self.stdout.write(f"-> Зависимость уже есть в {migration_file.name}, пропущено")
                    continue

                # Ищем строку dependencies = [
                lines = content.splitlines()
                new_lines = []
                added = False

                for line in lines:
                    new_lines.append(line)

                    if line.strip() == "dependencies = [" and not added:
                        new_lines.append(f"        {self.DEPENDENCY},")
                        added = True

                if added:
                    migration_file.write_text("\n".join(new_lines) + "\n")
                    self.stdout.write(f"-> Добавлена зависимость в {migrations_path}/{migration_file.name}")
                else:
                    self.stdout.write(f"-> Не найдено dependencies = [ в {migration_file.name}, пропущено")
