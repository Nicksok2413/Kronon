"""
Общие фикстуры для всех тестов проекта.
"""

import pytest
from asgiref.sync import sync_to_async
from django.conf import settings
from django.test import AsyncClient
from ninja_jwt.tokens import AccessToken

from apps.users.models import User, UserRole
from tests.utils.factories import UserFactory


@pytest.fixture
async def api_user() -> User:
    """
    Создает тестового пользователя (обычный линейный бухгалтер).

    Returns:
        User: Экземпляр модели обычного пользователя.
    """
    # Оборачиваем синхронную фабрику в sync_to_async
    # Это выполнит создание юзера в отдельном потоке, не блокируя Event Loop
    user: User = await sync_to_async(UserFactory)(role=UserRole.ACCOUNTANT)
    return user


@pytest.fixture
async def admin_user() -> User:
    """
    Создает тестового администратора (директора).

    Returns:
        User: Экземпляр модели администратора.
    """
    # Оборачиваем синхронную фабрику в sync_to_async
    # Это выполнит создание юзера в отдельном потоке, не блокируя Event Loop
    user: User = await sync_to_async(UserFactory)(role=UserRole.DIRECTOR)
    return user


@pytest.fixture
async def auth_client(api_user: User) -> AsyncClient:
    """
    Клиент (с JWT токеном) обычного линейного бухгалтера.

    Args:
        api_user (User): Фикстура обычного пользователя.

    Returns:
        AsyncClient: Клиент бухгалтера.
    """
    client = AsyncClient()

    # Генерируем JWT токен
    # Это CPU-bound операция (криптография), но иногда может лезть в БД (blacklist)
    # Безопаснее делать это явно, но AccessToken.for_user обычно синхронный и быстрый
    # Если ninja_jwt полезет в базу - обернем его в sync_to_async, но пока так:
    # TODO: sync_to_async
    token: str = str(AccessToken.for_user(api_user))

    client.defaults["Authorization"] = f"Bearer {token}"

    return client


@pytest.fixture
async def admin_client(admin_user: User) -> AsyncClient:
    """
    Клиент (с JWT токеном) администратора (директора).

    Args:
        admin_user (User): Фикстура администратора (директора).

    Returns:
        AsyncClient: Клиент администратора.
    """
    client = AsyncClient()

    # Генерируем JWT токен
    # Это CPU-bound операция (криптография), но иногда может лезть в БД (blacklist)
    # Безопаснее делать это явно, но AccessToken.for_user обычно синхронный и быстрый
    # Если ninja_jwt полезет в базу - обернем его в sync_to_async, но пока так:
    # TODO: sync_to_async
    token: str = str(AccessToken.for_user(admin_user))

    client.defaults["Authorization"] = f"Bearer {token}"

    return client


@pytest.fixture
async def system_client() -> AsyncClient:
    """
    Клиент с системным API-ключом (без JWT).

    Returns:
        AsyncClient: Клиент с системным API-ключом.
    """
    client = AsyncClient()

    client.defaults["X-API-Key"] = settings.INTERNAL_API_KEY

    return client
