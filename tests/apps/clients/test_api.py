"""
Интеграционные тесты для API клиентов.
"""

from time import perf_counter
from typing import Any

from asgiref.sync import sync_to_async
from django.test import AsyncClient

from apps.clients.models import Client
from apps.clients.schemas.client import ClientOut
from tests.utils.base import BaseAPITest
from tests.utils.factories import ClientFactory


class TestClientAPI(BaseAPITest):
    """
    Тестирование CRUD операций API Клиентов.

    Attributes:
        endpoint (str): Базовый URL эндпоинта.
    """

    endpoint: str = "/api/clients/"

    async def test_create_client_valid(self, admin_client: AsyncClient) -> None:
        """
        Проверка успешного создания клиента администратором.

        Args:
            admin_client: Авторизованный асинхронный клиент (с правами админа).
        """
        # Подготавливаем данные
        payload: dict[str, Any] = {
            "name": "Test Company",
            "unp": "191111111",  # Валидный тестовый УНП
            "org_type": "ooo",
            "tax_system": "usn_no_nds",
            "status": "onboarding",
            "contact_info": {"general_email": "test@test.com"},
        }

        # Выполняем запрос
        start = perf_counter()
        response = await admin_client.post(self.endpoint, data=payload, content_type="application/json")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=response, expected_status=201)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        json_response: dict[str, Any] = response.json()

        assert json_response["name"] == "Test Company"
        assert json_response["contact_info"]["general_email"] == "test@test.com"

        # Валидация схемы
        await self.validate_schema(data=json_response, schema=ClientOut)

        # Проверяем, что клиент реально создался в БД (асинхронно)
        assert await Client.objects.filter(id=json_response["id"]).aexists()

    async def test_get_client_list_paginated(self, auth_client: AsyncClient, api_user: Any) -> None:
        """Проверка получения списка клиентов с пагинацией и учетом OLP."""
        # Создаем 25 клиентов через фабрику, назначаем accountant=api_user, чтобы OLP пропустил их для бухгалтера
        # Используем create_batch внутри sync_to_async для оптимизации
        await sync_to_async(ClientFactory.create_batch)(25, accountant=api_user)

        # Запрашиваем первую страницу
        start = perf_counter()
        response_page_1 = await auth_client.get(f"{self.endpoint}?page=1")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=response_page_1, expected_status=200)

        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        json_response_page_1: dict[str, Any] = response_page_1.json()

        # Валидация схемы
        await self.validate_schema(data=json_response_page_1["items"], schema=ClientOut, many=True)

        # Проверка структуры пагинации Ninja: {items: [...], count: ...}
        assert len(json_response_page_1["items"]) == 20
        assert json_response_page_1["count"] == 25

        # Запрашиваем вторую страницу
        start = perf_counter()
        response_page_2 = await auth_client.get(f"{self.endpoint}?page=2")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=response_page_2, expected_status=200)

        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        json_response_page_2: dict[str, Any] = response_page_2.json()

        # Валидация схемы
        await self.validate_schema(data=json_response_page_2["items"], schema=ClientOut, many=True)

        # Проверка количества элементов второй страницы
        assert len(json_response_page_2["items"]) == 5

    async def test_soft_delete_and_restore(self, admin_client: AsyncClient) -> None:
        """Комплексная проверка Soft Delete и восстановления клиента."""

        # Создаем клиента
        client = await sync_to_async(ClientFactory)()

        # Мягкое удаление
        start = perf_counter()
        del_response = await admin_client.delete(f"{self.endpoint}{client.id}")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=del_response, expected_status=204)

        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        # Проверяем, что в списке активных его больше нет
        list_response = await admin_client.get(self.endpoint)
        assert list_response.json()["count"] == 0

        # Восстановление
        start = perf_counter()
        restore_response = await admin_client.patch(f"{self.endpoint}{client.id}/restore")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=restore_response, expected_status=200)

        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        # Валидация схемы
        await self.validate_schema(data=restore_response.json(), schema=ClientOut)

        # Проверяем, что он вернулся в список
        list_response_2 = await admin_client.get(self.endpoint)
        assert list_response_2.json()["count"] == 1
