""" """

import pytest
from asgiref.sync import sync_to_async
from django.test import AsyncClient
from ninja_jwt.tokens import AccessToken

from apps.users.models import User
from tests.utils.factories import UserFactory


@pytest.fixture
async def api_user() -> User:
    """
    Создает тестового пользователя.

    Returns:
        User: Экземпляр модели пользователя.
    """
    # Оборачиваем синхронную фабрику в sync_to_async
    # Это выполнит создание юзера в отдельном потоке, не блокируя Event Loop
    user: User = await sync_to_async(UserFactory)()
    return user


@pytest.fixture
async def auth_client(api_user: User) -> AsyncClient:
    """
    Создает авторизованного асинхронного клиента.

    Args:
        api_user: Фикстура пользователя.

    Returns:
        AsyncClient: Клиент с предустановленным заголовком Authorization.
    """
    client = AsyncClient()

    # Генерируем JWT токен
    # Это CPU-bound операция (криптография), но иногда может лезть в БД (blacklist)
    # Безопаснее делать это явно, но AccessToken.for_user обычно синхронный и быстрый
    # Если ninja_jwt полезет в базу - обернем его в sync_to_async, но пока так:
    # TODO: sync_to_async
    token: str = str(AccessToken.for_user(api_user))

    # Установка заголовков авторизации по умолчанию для всех запросов
    client.defaults["Authorization"] = f"Bearer {token}"
    return client
