"""
Тесты системы аутентификации, прав (RBAC) и объектных прав (OLP) API клиентов.
"""

from typing import Any

from asgiref.sync import sync_to_async
from django.test import AsyncClient

from apps.common.schemas import ErrorOut
from apps.users.models import UserRole
from tests.utils.base import BaseAPITest
from tests.utils.factories import ClientFactory, UserFactory


class TestClientSecurity(BaseAPITest):
    """
    Тестирование систем аутентификации и доступа к эндпойнтам API Клиентов.

    Attributes:
        endpoint (str): Базовый URL эндпоинта.
    """

    endpoint: str = "/api/clients/"

    # --- ТЕСТЫ OLP (Фильтрация списка) ---
    async def test_list_olp_isolation(self, auth_client: AsyncClient, api_user: Any):
        """Проверка: бухгалтер (api_user) видит только 'своих' клиентов."""
        # Создаем 'чужого' бухгалтера
        other_user = await sync_to_async(UserFactory)(role=UserRole.ACCOUNTANT)

        # Создаем клиентов: одного для api_user, второго для other_user
        my_client = await sync_to_async(ClientFactory)(accountant=api_user, name="My Client")
        other_client = await sync_to_async(ClientFactory)(accountant=other_user, name="Stranger Client")

        # Делаем запрос от api_user
        response = await auth_client.get(self.endpoint)
        data = response.json()

        # Проверяем, что в списке только my_client
        assert data["count"] == 1
        assert data["items"][0]["id"] == str(my_client.id)
        assert data["items"][0]["name"] == "My Client"

        # Убеждаемся, что чужого клиента нет в списке
        assert all(item["id"] != str(other_client.id) for item in data["items"])

    async def test_update_olp_forbidden(self, auth_client: AsyncClient) -> None:
        """Проверка OLP: бухгалтер не может обновить чужого клиента."""
        # Клиент без привязки к api_user
        client = await sync_to_async(ClientFactory)()

        response = await auth_client.patch(
            f"{self.endpoint}{client.id}", data={"name": "Hacked"}, content_type="application/json"
        )
        await self.assert_status(response=response, expected_status=403)

        # Проверяем формат ошибки
        await self.validate_schema(data=response.json(), schema=ErrorOut)

    # --- ТЕСТЫ RBAC (Доступ к эндпоинтам) ---
    async def test_delete_requires_admin_rbac(self, auth_client, api_user):
        """Проверка: обычный бухгалтер не может удалить даже 'своего' клиента."""
        # Создаем клиента для обычного бухгалтера
        client = await sync_to_async(ClientFactory)(accountant=api_user)

        # Пытаемся удалить (должно быть 403, так как это не админ)
        response = await auth_client.delete(f"{self.endpoint}{client.id}")
        assert response.status_code == 403  # Forbidden для бухгалтера

    async def test_admin_can_delete_anything(self, admin_client):
        """Проверка: администратор может удалить любого клиента."""

        # Создаем клиента
        target_client = await sync_to_async(ClientFactory)()

        response = await admin_client.delete(f"{self.endpoint}{target_client.id}")
        assert response.status_code == 204

    # --- ТЕСТЫ СИСТЕМНОГО API ---
    async def test_system_api_full_access(self, system_client: AsyncClient):
        """Проверка: системный ключ видит всё и обходит OLP/RBAC."""
        # Создаем 5 клиентов
        await sync_to_async(ClientFactory.create_batch)(5)

        # Запрос с системным API-ключом
        response = await system_client.get(self.endpoint)

        assert response.status_code == 200
        assert response.json()["count"] >= 5
