"""
Интеграционные тесты для API клиентов.
"""

from time import perf_counter
from typing import Any

from asgiref.sync import sync_to_async
from django.test import AsyncClient

from apps.clients.models import Client
from apps.clients.schemas.client import ClientOut
from apps.common.schemas import ErrorOut
from apps.users.models import User
from tests.utils.base import BaseAPITest
from tests.utils.factories import ClientFactory


class TestClientAPI(BaseAPITest):
    """Тестирование CRUD операций API Клиентов."""

    @property
    def endpoint(self) -> str:
        return self.get_url("clients")

    async def test_create_client_valid(self, admin_client: AsyncClient) -> None:
        """
        Проверка успешного создания клиента администратором.

        Args:
            admin_client (AsyncClient): Авторизованный асинхронный клиент (с правами админа).
        """

        # --- Arrange (подготовка) ---

        # Подготавливаем данные
        payload: dict[str, Any] = {
            "name": "Test Company",
            "unp": "191111111",  # Валидный тестовый УНП
            "org_type": "ooo",
            "tax_system": "usn_no_nds",
            "status": "onboarding",
            "contact_info": {"general_email": "test@test.com"},
        }

        # --- Act (действие) ---

        # Выполняем запрос
        response, data, elapsed_time = await self.make_request(
            admin_client.post(self.endpoint, data=payload, content_type="application/json")
        )

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=response, expected_status=201)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=700)
        # Валидация схемы
        await self.validate_schema(data=data, schema=ClientOut)

        assert data["name"] == "Test Company"
        assert data["contact_info"]["general_email"] == "test@test.com"

        # Проверяем, что клиент реально создался в БД (асинхронно)
        assert await Client.objects.filter(id=data["id"]).aexists()

    async def test_get_client_list_paginated(self, auth_client: AsyncClient, api_user: User) -> None:
        """
        Проверка получения списка клиентов с пагинацией и учетом OLP.

        Args:
            auth_client (AsyncClient): Авторизованный асинхронный клиент (с правами бухгалтера).
            api_user (User): Обычный пользователь (бухгалтер).
        """

        # --- Arrange (подготовка) ---

        # Создаем 25 клиентов через фабрику, назначаем accountant=api_user, чтобы OLP пропустил их для бухгалтера
        # Используем create_batch внутри sync_to_async для оптимизации
        await sync_to_async(ClientFactory.create_batch)(25, accountant=api_user)

        # --- Act (действие) ---

        # Запрашиваем первую страницу
        start = perf_counter()
        response_page_1 = await auth_client.get(f"{self.endpoint}?page=1")
        elapsed_time = perf_counter() - start

        data_page_1: dict[str, Any] = response_page_1.json()

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=response_page_1, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=700)
        # Валидация схемы
        await self.validate_schema(data=data_page_1["items"], schema=ClientOut, many=True)

        # Проверка структуры пагинации Ninja: {items: [...], count: ...}
        assert len(data_page_1["items"]) == 20
        assert data_page_1["count"] == 25

        # --- Act (действие) ---

        # Запрашиваем вторую страницу
        start = perf_counter()
        response_page_2 = await auth_client.get(f"{self.endpoint}?page=2")
        elapsed_time = perf_counter() - start

        data_page_2: dict[str, Any] = response_page_2.json()

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=response_page_2, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=700)
        # Валидация схемы
        await self.validate_schema(data=data_page_2["items"], schema=ClientOut, many=True)

        # Проверка количества элементов второй страницы
        assert len(data_page_2["items"]) == 5

    async def test_update_client_contact_info_deep_merge(self, admin_client: AsyncClient) -> None:
        """
        Проверка умного слияния JSON (patch_contact_data).
        Убеждаемся, что обновление email не затирает телефон.

        Args:
            admin_client (AsyncClient): Авторизованный асинхронный клиент (с правами админа).
        """

        # --- Arrange (подготовка) ---

        # Создаем клиента с контактами
        initial_contacts = {
            "general_email": "old@test.com",
            "general_phone": "+375291111111",
        }
        client = await sync_to_async(ClientFactory)(contact_info=initial_contacts)

        # Подготавливаем данные (обновляем только email)
        patch_payload = {"contact_info": {"general_email": "new@test.com"}}

        # --- Act (действие) ---

        # Патчим клиента
        start = perf_counter()
        patch_response = await admin_client.patch(
            f"{self.endpoint}{client.id}",
            data=patch_payload,
            content_type="application/json",
        )
        elapsed_time = perf_counter() - start

        data: dict[str, Any] = patch_response.json()

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=patch_response, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)
        # Валидация схемы
        await self.validate_schema(data=data, schema=ClientOut)

        # Проверяем, что email обновился
        assert data["contact_info"]["general_email"] == "new@test.com"
        # Проверяем, что телефон не исчез (Deep Merge сработал)
        assert data["contact_info"]["general_phone"] == "+375291111111"

    async def test_soft_delete_and_restore(self, admin_client: AsyncClient) -> None:
        """
        Комплексная проверка Soft Delete и восстановления клиента.

        Args:
            admin_client (AsyncClient): Авторизованный асинхронный клиент (с правами админа).
        """

        # --- Arrange (подготовка) ---

        # Создаем клиента
        client = await sync_to_async(ClientFactory)()

        # --- Act (действие) ---

        # Мягкое удаление
        start = perf_counter()
        del_response = await admin_client.delete(f"{self.endpoint}{client.id}")
        elapsed_time = perf_counter() - start

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=del_response, expected_status=204)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        # Проверяем, что в списке активных его больше нет
        list_response = await admin_client.get(self.endpoint)
        assert list_response.json()["count"] == 0

        # --- Act (действие) ---

        # Проверяем, что GET по ID выдает 404 (так как селектор фильтрует по active())
        start = perf_counter()
        get_response = await admin_client.get(f"{self.endpoint}{client.id}")
        elapsed_time = perf_counter() - start

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=get_response, expected_status=404)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)
        # Валидация схемы
        await self.validate_schema(data=get_response.json(), schema=ErrorOut)

        # --- Act (действие) ---

        # Восстановление
        start = perf_counter()
        restore_response = await admin_client.patch(f"{self.endpoint}{client.id}/restore")
        elapsed_time = perf_counter() - start

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=restore_response, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)
        # Валидация схемы
        await self.validate_schema(data=restore_response.json(), schema=ClientOut)

        # Проверяем, что он вернулся в список
        list_response_2 = await admin_client.get(self.endpoint)
        assert list_response_2.json()["count"] == 1

        # --- Act (действие) ---

        # Проверяем, что он доступен по ID
        start = perf_counter()
        get_response_2 = await admin_client.get(f"{self.endpoint}{client.id}")
        elapsed_time = perf_counter() - start

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=get_response_2, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)
        # Валидация схемы
        await self.validate_schema(data=restore_response.json(), schema=ClientOut)
