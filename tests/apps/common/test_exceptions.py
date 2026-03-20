"""
Тесты глобальных обработчиков исключений (Global Exception Handlers).
"""

from asgiref.sync import sync_to_async
from django.test import AsyncClient

from apps.common.schemas import ErrorOut
from tests.utils.base import BaseAPITest
from tests.utils.factories import ClientFactory


class TestGlobalExceptions(BaseAPITest):
    """Тестирование перехвата ошибок и приведения их к схеме ErrorOut."""

    endpoint: str = "/api/clients/"

    async def test_validation_error_422(self, admin_client: AsyncClient) -> None:
        """Проверка перехвата ошибок Pydantic/Ninja (422)."""
        payload = {
            "name": "A",
            "unp": "123",  # НЕВАЛИДНЫЙ УНП (нужно 9 цифр)
        }

        response = await admin_client.post(self.endpoint, data=payload, content_type="application/json")
        await self.assert_status(response=response, expected_status=422)

        data = response.json()
        assert data["code"] == "validation_error"
        assert "details" in data
        await self.validate_schema(data=data, schema=ErrorOut)

    async def test_integrity_error_409(self, admin_client: AsyncClient) -> None:
        """Проверка перехвата IntegrityError (409) при дубликате УНП."""
        client = await sync_to_async(ClientFactory)()

        payload = {
            "name": "Clone",
            "unp": client.unp,  # Пытаемся создать с существующим УНП
        }

        response = await admin_client.post(self.endpoint, data=payload, content_type="application/json")
        await self.assert_status(response=response, expected_status=409)

        data = response.json()
        assert data["code"] == "duplicate_unp"
        await self.validate_schema(data=data, schema=ErrorOut)

    async def test_not_found_404(self, admin_client: AsyncClient) -> None:
        """Проверка перехвата HttpError(404)."""
        # Генерируем несуществующий UUID
        fake_id = "019d0b27-0000-7000-8000-000000000000"

        response = await admin_client.get(f"{self.endpoint}{fake_id}")
        await self.assert_status(response=response, expected_status=404)

        data = response.json()
        assert data["code"] == "http_error_404"
        await self.validate_schema(data=data, schema=ErrorOut)
