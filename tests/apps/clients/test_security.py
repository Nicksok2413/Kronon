"""
Тесты системы аутентификации, прав (RBAC) и объектных прав (OLP) API клиентов.
"""

from time import perf_counter
from typing import Any

from asgiref.sync import sync_to_async
from django.test import AsyncClient

from apps.clients.schemas.client import ClientOut
from apps.common.schemas import ErrorOut
from apps.users.models import User, UserRole
from tests.utils.base import BaseAPITest
from tests.utils.factories import ClientFactory, UserFactory


class TestClientSecurity(BaseAPITest):
    """Тестирование систем аутентификации и доступа к эндпойнтам API Клиентов."""

    @property
    def endpoint(self) -> str:
        return self.get_url("clients")

    # --- ТЕСТЫ OLP (объектные права) ---

    async def test_client_list_olp_isolation(self, auth_client: AsyncClient, api_user: User) -> None:
        """
        Проверка: бухгалтер (api_user) видит только 'своих' клиентов.

        Args:
            auth_client (AsyncClient): Авторизованный асинхронный клиент (с правами бухгалтера).
            api_user (User): Обычный пользователь (бухгалтер).
        """

        # Создаем 'чужого' бухгалтера
        other_user = await sync_to_async(UserFactory)(role=UserRole.ACCOUNTANT)

        # Создаем клиентов: одного для api_user, второго для other_user
        my_client = await sync_to_async(ClientFactory)(accountant=api_user, name="My Client")
        other_client = await sync_to_async(ClientFactory)(accountant=other_user, name="Stranger Client")

        # Делаем запрос от api_user
        start = perf_counter()
        response = await auth_client.get(self.endpoint)
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=response, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        json_response: dict[str, Any] = response.json()

        # Валидация схемы
        await self.validate_schema(data=json_response["items"], schema=ClientOut, many=True)

        # Проверяем, что в списке только my_client
        assert json_response["count"] == 1
        assert json_response["items"][0]["id"] == str(my_client.id)
        assert json_response["items"][0]["name"] == "My Client"

        # Проверяем, что чужого клиента нет в списке
        assert all(item["id"] != str(other_client.id) for item in json_response["items"])

    async def test_client_update_olp(self, auth_client: AsyncClient, api_user: User) -> None:
        """
        Проверка OLP: бухгалтер может редактировать клиента, если он указан ответственным.

        Args:
            auth_client (AsyncClient): Авторизованный асинхронный клиент (с правами бухгалтера).
            api_user (User): Обычный пользователь (бухгалтер).
        """
        # Создаем клиента и назначаем api_user ответственным бухгалтером (accountant=api_user)
        client = await sync_to_async(ClientFactory)(accountant=api_user, name="Old Name")

        # Патчим клиента
        start = perf_counter()
        patch_response = await auth_client.patch(
            f"{self.endpoint}{client.id}",
            data={"name": "New Name"},
            content_type="application/json",
        )
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=patch_response, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        json_response: dict[str, Any] = patch_response.json()

        # Валидация схемы
        await self.validate_schema(data=json_response, schema=ClientOut)

        assert json_response["name"] == "New Name"

    async def test_client_update_olp_forbidden(self, auth_client: AsyncClient) -> None:
        """
        Проверка OLP: бухгалтер не может обновить чужого клиента.

        Args:
            auth_client (AsyncClient): Авторизованный асинхронный клиент (с правами бухгалтера).
        """
        # Создаем клиента (без привязки к api_user)
        client = await sync_to_async(ClientFactory)()

        # Патчим клиента
        start = perf_counter()
        patch_response = await auth_client.patch(
            f"{self.endpoint}{client.id}",
            data={"name": "Hacked"},
            content_type="application/json",
        )
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код (api_user получает 403)
        await self.assert_status(response=patch_response, expected_status=403)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        json_response: dict[str, Any] = patch_response.json()

        # Валидация схемы
        await self.validate_schema(data=json_response, schema=ErrorOut)

        assert "нет прав" in json_response["message"].lower()

    # --- ТЕСТЫ RBAC (Роли) ---

    async def test_client_delete_requires_admin_rbac(self, auth_client: AsyncClient, api_user: User) -> None:
        """
        Проверка: обычный бухгалтер не может удалить даже 'своего' клиента.

        Args:
            auth_client (AsyncClient): Авторизованный асинхронный клиент (с правами бухгалтера).
            api_user (User): Обычный пользователь (бухгалтер).
        """
        # Создаем клиента для обычного бухгалтера
        client = await sync_to_async(ClientFactory)(accountant=api_user)

        # Пытаемся удалить клиента от имени бухгалтера
        start = perf_counter()
        del_response = await auth_client.delete(f"{self.endpoint}{client.id}")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код (Forbidden для бухгалтера, так как он не админ)
        await self.assert_status(response=del_response, expected_status=403)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        json_response: dict[str, Any] = del_response.json()

        # Валидация схемы
        await self.validate_schema(data=json_response, schema=ErrorOut)

        assert "требуются права администратора" in json_response["message"].lower()

    async def test_client_restore_requires_admin_rbac(self, auth_client: AsyncClient, api_user: User) -> None:
        """
        Проверка: обычный бухгалтер не может восстанавливать даже 'своего' клиента.

        Args:
            auth_client (AsyncClient): Авторизованный асинхронный клиент (с правами бухгалтера).
            api_user (User): Обычный пользователь (бухгалтер).
        """

        # Создаем клиента для обычного бухгалтера
        client = await sync_to_async(ClientFactory)(accountant=api_user)

        # Удаляем клиента вручную через ORM
        await client.adelete()

        # Пытаемся восстановить от имени бухгалтера
        start = perf_counter()
        restore_response = await auth_client.patch(f"{self.endpoint}{client.id}/restore")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код (Forbidden для бухгалтера, так как он не админ)
        await self.assert_status(response=restore_response, expected_status=403)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        json_response: dict[str, Any] = restore_response.json()

        # Валидация схемы
        await self.validate_schema(data=json_response, schema=ErrorOut)

        assert "требуются права администратора" in json_response["message"].lower()

    async def test_admin_can_delete_anything(self, admin_client: AsyncClient) -> None:
        """
        Проверка: администратор может удалить любого клиента.

        Args:
            admin_client (AsyncClient): Авторизованный асинхронный клиент (с правами админа).
        """

        # Создаем клиента
        client = await sync_to_async(ClientFactory)()

        # Удаляем клиента от имени админа
        start = perf_counter()
        del_response = await admin_client.delete(f"{self.endpoint}{client.id}")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=del_response, expected_status=204)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

    async def test_admin_can_restore_anything(self, admin_client: AsyncClient) -> None:
        """
        Проверка: администратор может восстановить любого клиента.

        Args:
            admin_client (AsyncClient): Авторизованный асинхронный клиент (с правами админа).
        """

        # Создаем клиента
        client = await sync_to_async(ClientFactory)(name="Test Company")

        # Удаляем клиента вручную через ORM
        await client.adelete()

        # Восстанавливаем клиента от имени админа
        start = perf_counter()
        restore_response = await admin_client.patch(f"{self.endpoint}{client.id}/restore")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=restore_response, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        json_response: dict[str, Any] = restore_response.json()

        # Валидация схемы
        await self.validate_schema(data=json_response, schema=ClientOut)

        assert json_response["name"] == "Test Company"

    async def test_system_api_full_access(self, system_client: AsyncClient) -> None:
        """
        Проверка: системный ключ видит всё и обходит OLP/RBAC.


        Args:
            system_client (AsyncClient): Авторизованный асинхронный клиент (с системным API-ключом).
        """

        # --- Список клиентов ---

        # Создаем 5 клиентов
        await sync_to_async(ClientFactory.create_batch)(5)

        # Запрос списка клиентов
        start = perf_counter()
        list_response = await system_client.get(self.endpoint)
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=list_response, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        json_response: dict[str, Any] = list_response.json()

        # Валидация схемы
        await self.validate_schema(data=json_response["items"], schema=ClientOut, many=True)

        assert json_response["count"] >= 5

        # --- Создание клиента ---

        # Подготавливаем данные
        payload: dict[str, Any] = {
            "name": "Old Name",
            "unp": "191111111",  # Валидный тестовый УНП
            "org_type": "ooo",
            "tax_system": "usn_no_nds",
            "status": "onboarding",
            "contact_info": {"general_email": "test@test.com"},
        }

        # Создаем клиента
        start = perf_counter()
        create_response = await system_client.post(self.endpoint, data=payload, content_type="application/json")
        elapsed_time = perf_counter() - start

        # Статус код
        await self.assert_status(response=create_response, expected_status=201)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        create_json_response: dict[str, Any] = create_response.json()
        client_id = create_json_response["id"]

        # Валидация схемы
        await self.validate_schema(data=create_json_response, schema=ClientOut)

        assert create_json_response["name"] == "Old Name"
        assert create_json_response["contact_info"]["general_email"] == "test@test.com"

        # --- Обновление клиента ---

        # Патчим этого клиента
        start = perf_counter()
        patch_response = await system_client.patch(
            f"{self.endpoint}{client_id}",
            data={"name": "New Name"},
            content_type="application/json",
        )
        elapsed_time = perf_counter() - start

        # Статус код
        await self.assert_status(response=patch_response, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        patch_json_response: dict[str, Any] = patch_response.json()

        # Валидация схемы
        await self.validate_schema(data=patch_json_response, schema=ClientOut)

        assert patch_json_response["name"] == "New Name"

        # --- Удаление клиента ---

        # Удаляем этого клиента
        start = perf_counter()
        del_response = await system_client.delete(f"{self.endpoint}{client_id}")
        elapsed_time = perf_counter() - start

        # Статус код
        await self.assert_status(response=del_response, expected_status=204)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        # --- Восстановление клиента ---

        # Восстанавливаем этого клиента
        start = perf_counter()
        restore_response = await system_client.patch(f"{self.endpoint}{client_id}/restore")
        elapsed_time = perf_counter() - start

        # Статус код
        await self.assert_status(response=restore_response, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        restore_json_response: dict[str, Any] = restore_response.json()

        # Валидация схемы
        await self.validate_schema(data=restore_json_response, schema=ClientOut)

        assert restore_json_response["name"] == "New Name"
