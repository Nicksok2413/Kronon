"""
Базовый класс для асинхронных тестов API
"""

import json
from collections.abc import Awaitable
from time import perf_counter
from typing import Any

import pytest
from pydantic import BaseModel, ValidationError


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class BaseAPITest:
    """
    Базовый класс для асинхронных тестов API с поддержкой БД.

    Предоставляет методы для проверки статус-кодов, времени ответа API
    и валидации Pydantic-схем с информативным выводом ошибок в формате JSON.
    """

    # Текущая версия API
    api_version: str = "v1"

    @classmethod
    def get_url(cls, path: str) -> str:
        """
        Формирует полный URL с учетом версии API.

        Args:
            path (str): Путь эндпоинта (например, 'clients' или 'clients/123').

        Returns:
            str: Сформированный URL (например, '/api/v1/clients/').
        """
        # Убираем лишние слэши по краям, чтобы избежать //
        clean_path = path.strip("/")

        return f"/api/{cls.api_version}/{clean_path}/"

    @classmethod
    async def validate_schema(
        cls,
        data: dict[str, Any] | list[dict[str, Any]],
        schema: type[BaseModel],
        many: bool = False,
    ) -> BaseModel | list[BaseModel]:
        """
        Проверяет соответствие данных схеме Pydantic.

        Args:
            data (dict[str, Any] | list[dict[str, Any]]): Данные для валидации (словарь или список).
            schema (type[BaseModel]): Класс Pydantic схемы (например, ClientOut).
            many (bool): True, если ожидается список объектов.

        Returns:
            Валидированный объект или список объектов схемы.
        """
        try:
            if many and isinstance(data, list):
                return [schema.model_validate(item) for item in data]

            return schema.model_validate(data)

        except ValidationError as exc:
            # Выводим ошибки валидации в читаемом виде
            error_detail = json.dumps(exc.errors(), indent=2, ensure_ascii=False)
            pytest.fail(f"Pydantic Validation Failed:\n{error_detail}")

    @classmethod
    async def assert_status(cls, response: Any, expected_status: int) -> None:
        """
        Проверяет HTTP статус-код и выводит тело ответа при несовпадении.

        Args:
            response (Any): Объект ответа от AsyncClient.
            expected_status (int): Ожидаемый HTTP статус-код (например, 200 или 201).

        Raises:
            AssertionError: Если коды не совпадают.
        """
        if response.status_code != expected_status:
            try:
                # Пытаемся распарсить JSON для красивого вывода
                body = response.json()
                error_msg = json.dumps(body, indent=2, ensure_ascii=False)
            except (
                ValueError,
                AttributeError,
            ):
                # Если не JSON (например, 500 ошибка с HTML), берем сырой текст
                error_msg = response.content.decode("utf-8")

            pytest.fail(
                f"\nStatus Check Failed!"
                f"\nExpected: {expected_status}"
                f"\nActual:   {response.status_code}"
                f"\nBody:     {error_msg}"
            )

    @classmethod
    async def assert_performance(cls, elapsed_time: float, max_ms: int = 500) -> None:
        """
        Проверяет, уложился ли запрос в отведенное время.

        Args:
            elapsed_time: Время выполнения в секундах (результат time.perf_counter()).
            max_ms: Лимит в миллисекундах.
        """
        actual_ms = elapsed_time * 1000

        if actual_ms > max_ms:
            pytest.fail(f"API too slow! Response took: {actual_ms:.2f}ms, Limit: {max_ms}ms")

    @classmethod
    async def make_request(cls, request_awaitable: Awaitable[Any]) -> tuple[Any, Any, float]:
        """
        Выполняет HTTP-запрос, замеряет время выполнения и безопасно извлекает JSON.

        Args:
            request_awaitable (Awaitable[Any]): Awaitable объект (корутина) запроса от AsyncClient.

        Returns:
            tuple[Any, Any, float]: (Объект ответа, Распарсенный JSON или None, Время в миллисекундах).
        """
        start = perf_counter()

        # Выполняем переданный запрос (Event Loop переключается сюда)
        response = await request_awaitable

        elapsed_time = perf_counter() - start

        # Пытаемся извлечь JSON
        try:
            data = response.json()
        except ValueError, AttributeError:
            data = None

        return response, data, elapsed_time
