"""
Интеграционные тесты для публичного справочника сотрудников (Directory API).
"""

from time import perf_counter
from typing import Any

from asgiref.sync import sync_to_async
from django.test import AsyncClient

from apps.users.schemas.directory import UserDirectoryOut
from tests.utils.base import BaseAPITest
from tests.utils.factories import UserFactory


class TestDirectoryAPI(BaseAPITest):
    """
    Тестирование API Справочника сотрудников.
    Доступно всем авторизованным пользователям.
    """

    @property
    def endpoint(self) -> str:
        return self.get_url("directory")

    async def test_get_directory_list(self, auth_client: AsyncClient) -> None:
        """
        Проверка получения списка активных сотрудников.
        Убеждаемся, что приватные HR-поля не "утекают" в ответ.

        Args:
            auth_client (AsyncClient): Авторизованный асинхронный клиент (с правами бухгалтера).
        """

        # --- Arrange (подготовка) ---

        # Создаем пару активных юзеров и одного уволенного
        await sync_to_async(UserFactory.create_batch)(3, is_active=True)
        await sync_to_async(UserFactory)(is_active=False, email="fired@kronon.by")

        # --- Act (действие) ---

        # Выполняем запрос
        start = perf_counter()
        response = await auth_client.get(self.endpoint)
        elapsed_time = perf_counter() - start

        data: dict[str, Any] = response.json()

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=response, expected_status=200)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)
        # Валидация схемы (Pydantic сам проверит, что лишних полей нет)
        await self.validate_schema(data=data["items"], schema=UserDirectoryOut, many=True)

        # Проверяем, что уволенный сотрудник не попал в выдачу
        emails = [user["email"] for user in data["items"]]
        assert "fired@kronon.by" not in emails

        # Проверяем, что приватных полей нет в ответе
        assert "contract_start_date" not in data["items"][0]

    async def test_get_directory_user_not_found(self, auth_client: AsyncClient) -> None:
        """
        Проверка получения 404 при запросе несуществующего (или уволенного) сотрудника.

        Args:
            auth_client (AsyncClient): Авторизованный асинхронный клиент (с правами бухгалтера).
        """

        # --- Arrange (подготовка) ---

        fired_user = await sync_to_async(UserFactory)(is_active=False)

        # --- Act (действие) ---

        # Выполняем запрос
        start = perf_counter()
        response = await auth_client.get(f"{self.endpoint}{fired_user.id}")
        elapsed_time = perf_counter() - start

        data = response.json()

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=response, expected_status=404)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        assert data["code"] == "http_error_404"
