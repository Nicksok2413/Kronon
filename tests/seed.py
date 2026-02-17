"""
Скрипт для наполнения БД тестовыми данными.
Запускается через: python -m tests.seed
"""

import os
import random
import sys

import django
from loguru import logger as log

# Настройка окружения Django
# Нужно указать, где лежат настройки, перед импортом моделей
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

from django.conf import settings
from django.db import transaction

from apps.users.models import UserRole
from tests.utils.factories import ClientFactory, DepartmentFactory, UserFactory


def create_structure() -> None:
    """Создает отделы, сотрудников и клиентов."""

    # Отделы
    departments_names = ["Бухгалтерия ИП", "Бухгалтерия ЮЛ", "Кадры", "Администрация"]
    departments = []

    for name in departments_names:
        department = DepartmentFactory(name=name)
        departments.append(department)

    log.info(f"Создано отделов: {len(departments)}")

    # Сотрудники
    users = []

    # Главбух
    head_accountant = UserFactory(
        email="head@kronon.by",
        role=UserRole.CHIEF_ACCOUNTANT,
        department=departments[3],  # Администрация
    )
    head_accountant.set_password("password")
    head_accountant.save()
    users.append(head_accountant)

    for department in departments:
        # По 2 бухгалтера на отдел
        for _ in range(2):
            user = UserFactory(department=department, role=UserRole.ACCOUNTANT)
            user.set_password("password")
            user.save()
            users.append(user)

    log.info(f"Создано сотрудников: {len(users)}")

    # Клиенты
    clients_count = 10

    for _ in range(clients_count):
        accountant = random.choice(users)
        payroll_accountant = random.choice(users)

        ClientFactory(accountant=accountant, payroll_accountant=payroll_accountant, department=accountant.department)

    log.info(f"Создано клиентов: {clients_count}")


if __name__ == "__main__":
    if not settings.DEBUG:
        log.error("⚠️ ВНИМАНИЕ: Попытка запустить сидинг на PRODUCTION-окружении! Прерывание.")
        sys.exit(1)

    log.info("Начинаем наполнение базы данных...")

    try:
        with transaction.atomic():
            create_structure()
        log.success("БД успешно наполнена тестовыми данными.")
    except Exception as exc:
        log.exception(f"Ошибка при наполнении БД: {exc}")
        sys.exit(1)
