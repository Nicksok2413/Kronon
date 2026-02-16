"""
Команда для автоматического создания суперпользователя при старте приложения.
Берет данные из переменных окружения.
"""

from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.users.models import User


class Command(BaseCommand):
    help = "Создает суперпользователя, если он не существует (идемпотентно)."

    def handle(self, *args: Any, **options: Any) -> None:
        # Получаем учетные данные из настроек (которые берутся из .env)
        email = settings.ADMIN_EMAIL
        password = settings.ADMIN_PASSWORD

        if not email or not password:
            self.stdout.write(self.style.WARNING("Переменные ADMIN_EMAIL или ADMIN_PASSWORD не заданы. Пропуск."))
            return None

        user_exists = User.objects.filter(email=email).exists()

        if user_exists:
            self.stdout.write(self.style.SUCCESS(f"Суперпользователь {email} уже существует."))
        else:
            User.objects.create_superuser(email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Суперпользователь {email} успешно создан."))

        return None
