import pytest
from ninja_jwt.tokens import AccessToken

from tests.utils.factories import ClientFactory, UserFactory

# Маркер для всех тестов в этом файле
pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def auth_headers():
    """Фикстура для получения заголовков авторизации."""
    user = UserFactory()
    token = AccessToken.for_user(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_client_create(client, auth_headers):
    """Тест создания клиента через API."""
    data = {
        "name": "Test Company",
        "unp": "191111111",  # Валидный УНП
        "org_type": "ooo",
        "tax_system": "usn_no_nds",
        "status": "onboarding",
    }

    # client - это AsyncClient из pytest-django (если установлен pytest-asyncio)
    response = await client.post("/api/clients/", data=data, content_type="application/json", **auth_headers)

    assert response.status_code == 201
    json_resp = response.json()
    assert json_resp["name"] == "Test Company"
    assert json_resp["id"] is not None


@pytest.mark.asyncio
async def test_client_list_pagination(client, auth_headers):
    """Тест списка и пагинации."""
    # Создаем 25 клиентов через фабрику (синхронно, так как фабрики пока синхронные)
    # Чтобы использовать sync фабрики в async тесте, нужно обернуть или использовать sync_db
    # Но проще использовать sync_to_async адаптер для фабрик или создать их заранее
    await _create_batch_clients(25)

    response = await client.get("/api/clients/?page=1", **auth_headers)
    assert response.status_code == 200
    data = response.json()

    # Ninja пагинация возвращает {items: [...], count: ...}
    assert len(data["items"]) == 20  # page_size по умолчанию
    assert data["count"] == 25


async def _create_batch_clients(count):
    from asgiref.sync import sync_to_async

    # Обертка для массового создания
    for _ in range(count):
        await sync_to_async(ClientFactory)()
