"""
Тесты глобальных обработчиков исключений (Global Exception Handlers).
"""

from time import perf_counter
from typing import Any

from asgiref.sync import sync_to_async
from django.test import AsyncClient

from apps.common.schemas import ErrorOut
from tests.utils.base import BaseAPITest
from tests.utils.factories import ClientFactory


class TestGlobalExceptions(BaseAPITest):
    """Тестирование перехвата ошибок и приведения их к схеме ErrorOut."""

    @property
    def endpoint(self) -> str:
        return self.get_url("clients")

    async def test_validation_error_422(self, admin_client: AsyncClient) -> None:
        """
        Проверка перехвата ошибок Pydantic/Ninja ValidationError (422).

        Args:
            admin_client (AsyncClient): Авторизованный асинхронный клиент (с правами админа).
        """
        # Подготавливаем данные
        payload = {
            "name": "A",
            "unp": "123",  # НЕВАЛИДНЫЙ УНП (нужно 9 цифр)
        }

        # Выполняем запрос
        start = perf_counter()
        response = await admin_client.post(self.endpoint, data=payload, content_type="application/json")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=response, expected_status=422)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        json_response: dict[str, Any] = response.json()

        # Валидация схемы
        await self.validate_schema(data=json_response, schema=ErrorOut)

        assert json_response["code"] == "validation_error"
        assert "details" in json_response
        assert "unp" in str(json_response["details"])

    async def test_integrity_error_409(self, admin_client: AsyncClient) -> None:
        """
        Проверка перехвата IntegrityError (409) при дубликате УНП.

        Args:
            admin_client (AsyncClient): Авторизованный асинхронный клиент (с правами админа).
        """

        # Создаем клиента
        client = await sync_to_async(ClientFactory)()

        # Подготавливаем данные
        payload = {
            "name": "Clone",
            "unp": client.unp,  # Пытаемся создать с существующим УНП
        }

        # Выполняем запрос
        start = perf_counter()
        response = await admin_client.post(self.endpoint, data=payload, content_type="application/json")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=response, expected_status=409)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        json_response: dict[str, Any] = response.json()

        # Валидация схемы
        await self.validate_schema(data=json_response, schema=ErrorOut)

        assert json_response["code"] == "duplicate_unp"
        assert "УНП" in json_response["message"]

    async def test_not_found_404(self, admin_client: AsyncClient) -> None:
        """
        Проверка перехвата HttpError(404).

        Args:
            admin_client (AsyncClient): Авторизованный асинхронный клиент (с правами админа).
        """
        # Генерируем несуществующий UUID
        fake_id = "019d0b27-0000-7000-8000-000000000000"

        # Выполняем запрос
        start = perf_counter()
        response = await admin_client.get(f"{self.endpoint}{fake_id}")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=response, expected_status=404)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        json_response: dict[str, Any] = response.json()

        # Валидация схемы
        await self.validate_schema(data=json_response, schema=ErrorOut)

        assert json_response["code"] == "http_error_404"
