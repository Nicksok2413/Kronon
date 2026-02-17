"""
Фабрики для генерации тестовых данных (Factory Boy).
"""

import random

import factory
from django.contrib.auth.hashers import make_password
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.clients.models import Client, ClientStatus, OrganizationType, TaxSystem
from apps.users.models import Department, User, UserRole
from tests.utils.unp import generate_valid_unp


class DepartmentFactory(DjangoModelFactory):
    """Фабрика для отделов."""

    class Meta:
        model = Department
        django_get_or_create = ("name",)

    name = factory.Faker("job")  # Генерируем случайные названия


class UserFactory(DjangoModelFactory):
    """Фабрика для сотрудников."""

    class Meta:
        model = User

    email = factory.Faker("email")
    first_name = factory.Faker("first_name", locale="ru_RU")
    last_name = factory.Faker("last_name", locale="ru_RU")
    # Хешируем пароль сразу, чтобы можно было войти
    password = factory.LazyFunction(lambda: make_password("password"))

    role = factory.Iterator(UserRole.values)
    department = factory.SubFactory(DepartmentFactory)

    is_active = True
    is_staff = True  # Чтобы пускало в админку


class ClientFactory(DjangoModelFactory):
    """Фабрика для клиентов."""

    class Meta:
        model = Client

    name = factory.Faker("company", locale="ru_RU")
    full_legal_name = factory.LazyAttribute(lambda o: f"OOO {o.name}")
    unp = factory.LazyFunction(generate_valid_unp)

    org_type = factory.Iterator(OrganizationType.values)
    tax_system = factory.Iterator(TaxSystem.values)
    status = factory.Iterator(ClientStatus.values)

    # JSON поле генерируем как словарь
    contact_info = factory.LazyAttribute(
        lambda o: {
            "general_email": f"info@{o.name.replace(' ', '').lower()}.by",
            "general_phone": "+37529" + str(random.randint(1000000, 9999999)),
            "contacts": [{"role": "Директор", "full_name": "Иванов Иван Иванович", "phone": "+375291234567"}],
        }
    )

    created_at = factory.Faker("date_time_this_year", tzinfo=timezone.get_current_timezone())
