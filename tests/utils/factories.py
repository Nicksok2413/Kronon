"""
Фабрики для генерации тестовых данных (Factory Boy).
"""

import random

import factory
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from django.utils.text import slugify
from factory.django import DjangoModelFactory

from apps.clients.models import Client, ClientStatus, OrganizationType, TaxSystem
from apps.users.models import Department, User, UserRole
from tests.utils.unp import generate_valid_unp


class DepartmentFactory(DjangoModelFactory):
    """Фабрика для отделов."""

    class Meta:
        model = Department
        django_get_or_create = ("name",)

    name: str = factory.Faker("job")  # Генерируем случайные названия


class UserFactory(DjangoModelFactory):
    """Фабрика для сотрудников."""

    class Meta:
        model = User

    email: str = factory.Faker("email")
    first_name: str = factory.Faker("first_name", locale="ru_RU")
    last_name: str = factory.Faker("last_name", locale="ru_RU")
    # Хешируем пароль сразу, чтобы можно было войти
    password: str = factory.LazyFunction(lambda: make_password("password"))

    role: str = factory.Iterator(UserRole.values)
    department: str = factory.SubFactory(DepartmentFactory)

    is_active: bool = True
    is_staff: bool = True  # Чтобы пускало в админку


class ClientFactory(DjangoModelFactory):
    """Фабрика для клиентов."""

    class Meta:
        model = Client

    name: str = factory.Faker("company", locale="ru_RU")
    unp: str = factory.LazyFunction(generate_valid_unp)

    org_type: str = factory.Iterator(OrganizationType.values)
    tax_system: str = factory.Iterator(TaxSystem.values)
    status: str = factory.Iterator(ClientStatus.values)

    @factory.lazy_attribute
    def full_legal_name(self) -> str:
        """Генерирует полное название на основе типа организации."""
        return f"{self.org_type.upper()} {self.name}"

    # Генерация безопасного contact_info (JSON поле)
    @factory.lazy_attribute
    def contact_info(self):
        # Превращаем "ЗАО «Рога и Копыта»" в "zao-roga-i-kopyta"
        safe_name = slugify(self.name)

        # Если slug пустой (все символы удалились), генерируем рандом
        if not safe_name:
            safe_name = f"client-{random.randint(1000, 9999)}"

        email = f"info@{safe_name}.by"

        return {
            "general_email": email,
            "general_phone": "+37529" + str(random.randint(1000000, 9999999)),
            "contacts": [{"role": "Директор", "full_name": "Иванов Иван Иванович", "phone": "+375291234567"}],
        }

    created_at = factory.Faker("date_time_this_year", tzinfo=timezone.get_current_timezone())
