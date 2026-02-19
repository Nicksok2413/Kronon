""" """

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
class BaseAPITest:
    """Базовый класс для асинхронных тестов API с поддержкой БД."""

    @classmethod
    def validate_schema(
        cls,
        data: dict[str, Any] | list[dict[str, Any]],
        schema: type[BaseModel],
        many: bool = False,
    ) -> BaseModel | list[BaseModel]:
        """
        Проверяет соответствие данных схеме Pydantic.

        Args:
            data (dict[str, Any] | list[dict[str, Any]]): Данные для валидации (словарь или список).
            schema (Type[BaseModel]): Класс Pydantic схемы.
            many (bool): Флаг, указывающий на список объектов.

        Returns:
            Экземпляр схемы или список экземпляров.

        Raises:
            pytest.fail: Если данные не соответствуют схеме.
        """
        try:
            if many and isinstance(data, list):
                return [schema.model_validate(item) for item in data]

            return schema.model_validate(data)

        except ValidationError as exc:
            pytest.fail(f"API Schema Validation Error: {exc.json()}")

    @classmethod
    async def assert_status(cls, response: Any, expected_status: int) -> None:
        """
        Проверяет статус-код ответа.

        Args:
            response (Any): Объект ответа от AsyncClient.
            expected_status (int): Ожидаемый HTTP статус-код.

        Returns:
            None

        Raises:
            AssertionError: При несовпадении статусов.
        """
        content: str = response.content.decode("utf-8")

        assert response.status_code == expected_status, (
            f"Expected {expected_status}, got {response.status_code}. Body: {content}"
        )
