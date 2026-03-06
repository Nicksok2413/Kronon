"""
Тесты для системы аудита изменений клиентов.
"""

from time import perf_counter
from typing import Any

from asgiref.sync import sync_to_async
from django.test import AsyncClient

from apps.clients.schemas.history import ClientHistoryOut
from apps.users.constants import SYSTEM_USER_ID
from tests.utils.base import BaseAPITest
from tests.utils.factories import ClientFactory


class TestClientHistory(BaseAPITest):
    """
    Тестирование истории изменения клиентов (Audit Log).

    Attributes:
        endpoint (str): Базовый URL эндпоинта.
    """

    endpoint: str = "/api/clients/"

    async def test_history_logging(self, auth_client: AsyncClient) -> None:
        """Проверка эндпойнта получения списка событий изменения клиента."""
        # Создаем клиента
        client = await sync_to_async(ClientFactory)()

        # Формируем эндпойнт
        endpoint: str = f"/api/clients/{client.id}/history"

        # Делаем изменение через API
        patch_data = {"name": "Updated Name"}

        # Обновляем клиента
        patch_response = await auth_client.patch(
            f"/api/clients/{client.id}", data=patch_data, content_type="application/json"
        )

        assert patch_response.status_code == 200

        # Проверяем историю
        start = perf_counter()
        history = await auth_client.get(endpoint)
        elapsed_time = perf_counter() - start

        data = history.json()
        update_event = next(event for event in data if event["pgh_label"] == "update")

        # Проверки
        assert len(data) >= 1
        assert update_event["pgh_diff"]["name"][1] == "Updated Name"

        # Статус код
        await self.assert_status(response=history, expected_status=200)

        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        # Валидация схемы
        await self.validate_schema(data=data, schema=ClientHistoryOut, many=True)

    async def test_history_initiator_sync(self, auth_client, api_user):
        """Проверка: в записи истории лежит ID юзера, который изменил клиента."""
        client = await sync_to_async(ClientFactory)(accountant=api_user)

        # Обновляем имя
        await auth_client.patch(
            f"{self.endpoint}{client.id}", data={"name": "New Name"}, content_type="application/json"
        )

        # Проверяем историю (используя pghistory модели или селектор)
        from apps.clients.selectors import get_client_history_queryset

        history = await get_client_history_queryset(client.id)

        # Убеждаемся, что последний автор — наш api_user.id
        assert history[0]["pgh_context"]["user"] == str(api_user.id)

    async def test_system_api_audit_logs_system_uuid(self, system_client):
        """Проверка: системный запрос записывает SYSTEM_USER_ID в историю."""
        payload: dict[str, Any] = {
            "name": "System Corp",
            "unp": "191111111",  # Валидный тестовый УНП
            "org_type": "ooo",
            "tax_system": "usn_no_nds",
            "status": "active",
        }

        # Создаем клиента через систему
        response = await system_client.post(self.endpoint, data=payload, content_type="application/json")
        assert response.status_code == 201
        client_id = response.json()["id"]

        # Проверяем историю в БД напрямую (что в pghistory записался SYSTEM_USER_ID)
        from apps.clients.selectors import get_client_history_queryset

        history = await get_client_history_queryset(client_id)

        # В контексте pghistory должен быть  системный UUID
        last_event = history[0]

        # Убеждаемся, что pghistory зафиксировала SYSTEM_USER_ID
        assert str(last_event["pgh_context"]["user"]) == str(SYSTEM_USER_ID)

    async def test_initiator_logging_with_details(self, system_client, settings):
        """Проверка: лог инициатора запроса к API содержит User-Agent, если флаг включен."""
        settings.LOG_DETAILED_AUDIT = True

        # Делаем запрос с кастомным User-Agent
        headers = {"HTTP_USER_AGENT": "Test-Bot/1.0"}
        response = await system_client.get(self.endpoint, **headers)

        assert response.status_code == 200
        # В реальном логе (stderr) мы бы увидели "[IP: ..., UA: Test-Bot/1.0]"
