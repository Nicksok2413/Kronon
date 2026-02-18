"""
Интеграционные тесты для API клиентов.
"""

import pytest
from asgiref.sync import sync_to_async
from django.test import AsyncClient
from ninja_jwt.tokens import AccessToken

from apps.clients.models import Client
from tests.utils.factories import ClientFactory, UserFactory

# Маркер для доступа к БД (transaction=True важен для очистки после тестов)
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
async def auth_headers() -> dict[str, str]:
    """
    Асинхронная фикстура для получения заголовков авторизации.
    Создает пользователя и генерирует JWT токен.

    Returns:
        dict[str, str]: Заголовок Authorization.
    """
    # Оборачиваем синхронную фабрику в sync_to_async
    # Это выполнит создание юзера в отдельном потоке, не блокируя Event Loop
    user = await sync_to_async(UserFactory)()

    # Генерация токена - операция CPU-bound (криптография),
    # но иногда может лезть в БД (если включен blacklist)
    # Безопаснее делать это явно, но AccessToken.for_user обычно синхронный и быстрый
    # Если ninja_jwt полезет в базу - обернем и его, но пока так:
    token = str(AccessToken.for_user(user))

    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_client_create(async_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """
    Тест создания клиента через API (POST).
    """
    data = {
        "name": "Test Company",
        "unp": "191111111",  # Валидный тестовый УНП
        "org_type": "ooo",
        "tax_system": "usn_no_nds",
        "status": "onboarding",
    }

    response = await async_client.post("/api/clients/", data=data, content_type="application/json", **auth_headers)

    assert response.status_code == 201
    json_resp = response.json()
    assert json_resp["name"] == "Test Company"
    assert json_resp["id"] is not None

    # Проверяем, что клиент реально создался в БД (асинхронно)
    assert await Client.objects.filter(id=json_resp["id"]).aexists()


@pytest.mark.asyncio
async def test_client_list_pagination(async_client: AsyncClient, auth_headers: dict[str, str]) -> None:
    """
    Тест получения списка клиентов и работы пагинации.
    """
    # Создаем 25 клиентов через фабрику
    # Используем create_batch внутри sync_to_async для оптимизации
    await sync_to_async(ClientFactory.create_batch)(25)

    # Запрашиваем первую страницу
    response = await async_client.get("/api/clients/?page=1", **auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Формат ответа Ninja Pagination: {items: [...], count: ...}
    assert len(data["items"]) == 20
    assert data["count"] == 25

    # Запрашиваем вторую страницу
    response_page_2 = await async_client.get("/api/clients/?page=2", **auth_headers)
    assert response_page_2.status_code == 200
    data_page_2 = response_page_2.json()

    assert len(data_page_2["items"]) == 5
