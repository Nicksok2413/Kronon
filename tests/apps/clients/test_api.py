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
    """Тестирование CRUD операций API Клиентов.

    Attributes:
        endpoint: Базовый URL эндпоинта.
    """

    endpoint: str = "/api/clients/"

    async def test_create_client_valid(self, auth_client: AsyncClient) -> None:
        """
        Проверка успешного создания клиента.

        Args:
            auth_client: Авторизованный асинхронный клиент.
        """
        # Подготавливаем данные
        payload: dict[str, Any] = {
            "name": "Test Company",
            "unp": "191111111",  # Валидный тестовый УНП
            "org_type": "ooo",
            "tax_system": "usn_no_nds",
            "status": "onboarding",
        }

        # Выполняем запрос
        start = perf_counter()
        response = await auth_client.post(self.endpoint, data=payload, content_type="application/json")
        end = perf_counter()

        json_response: dict[str, Any] = response.json()

        # Проверки
        assert json_response["name"] == "Test Company"
        assert json_response["id"] is not None

        # Статус код
        await self.assert_status(response=response, expected_status=201)

        # Время ответа API
        await self.assert_performance(end - start, max_ms=300)

        # Валидация схемы
        await self.validate_schema(data=json_response, schema=ClientOut)

        # Проверяем, что клиент реально создался в БД (асинхронно)
        assert await Client.objects.filter(id=json_response["id"]).aexists()

    async def test_get_client_list_paginated(self, auth_client: AsyncClient) -> None:
        """
        Проверка получения списка клиентов с пагинацией.

        Args:
            auth_client: Авторизованный асинхронный клиент.
        """
        # Создаем 25 клиентов через фабрику
        # Используем create_batch внутри sync_to_async для оптимизации
        await sync_to_async(ClientFactory.create_batch)(25)

        # Запрашиваем первую страницу
        start = perf_counter()
        response_page_1 = await auth_client.get(f"{self.endpoint}?page=1")
        end = perf_counter()

        json_response_page_1: dict[str, Any] = response_page_1.json()

        # Статус код
        await self.assert_status(response=response_page_1, expected_status=200)

        # Время ответа API
        await self.assert_performance(end - start, max_ms=300)

        # Валидация схемы
        await self.validate_schema(data=json_response_page_1["items"], schema=ClientOut, many=True)

        # Проверка структуры пагинации Ninja: {items: [...], count: ...}
        assert len(json_response_page_1["items"]) == 20
        assert json_response_page_1["count"] == 25

        # Запрашиваем вторую страницу
        start = perf_counter()
        response_page_2 = await auth_client.get(f"{self.endpoint}?page=2")
        end = perf_counter()

        json_response_page_2: dict[str, Any] = response_page_2.json()

        # Статус код
        await self.assert_status(response=response_page_2, expected_status=200)

        # Время ответа API
        await self.assert_performance(end - start, max_ms=300)

        # Валидация схемы
        await self.validate_schema(data=json_response_page_2["items"], schema=ClientOut, many=True)

        # Проверка количества элементов второй страницы
        assert len(json_response_page_2["items"]) == 5
