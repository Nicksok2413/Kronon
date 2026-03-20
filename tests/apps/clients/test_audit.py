"""
Тесты для системы аудита изменений клиентов.
"""

from time import perf_counter
from typing import Any

from asgiref.sync import sync_to_async
from django.test import AsyncClient

from apps.audit.schemas import ClientHistoryOut
from apps.users.constants import SYSTEM_USER_ID
from tests.utils.base import BaseAPITest
from tests.utils.factories import ClientFactory


class TestClientHistory(BaseAPITest):
    """
    Тестирование истории изменения клиентов (Audit Log).

    Attributes:
        endpoint (str): Базовый URL эндпоинта.
    """

    endpoint: str = "/api/audit/clients/"

    async def test_history_logging(self, admin_client: AsyncClient) -> None:
        """Проверка эндпойнта получения списка событий изменения клиента."""
        # Создаем клиента
        client = await sync_to_async(ClientFactory)()

        # Делаем изменение через API
        patch_data = {"name": "Updated Name"}

        # Обновляем клиента от имени админа
        await admin_client.patch(f"/api/clients/{client.id}", data=patch_data, content_type="application/json")

        # Запрашиваем историю от имени админа
        start = perf_counter()
        history = await admin_client.get(f"{self.endpoint}{client.id}")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=history, expected_status=200)

        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        data = history.json()

        # Валидация схемы
        await self.validate_schema(data=data, schema=ClientHistoryOut, many=True)

        update_event = next(event for event in data if event["pgh_label"] == "update")
        assert len(data) >= 1
        assert update_event["pgh_diff"]["name"][1] == "Updated Name"

    async def test_history_initiator_sync(self, auth_client: AsyncClient, api_user: Any):
        """Проверка записи ID пользователя, изменившего клиента."""
        client = await sync_to_async(ClientFactory)(accountant=api_user)

        # Обновляем имя
        await auth_client.patch(f"/api/clients/{client.id}", data={"name": "New Name"}, content_type="application/json")

        # Проверяем историю используя  селектор
        from apps.audit.selectors import get_client_history_queryset

        history = await get_client_history_queryset(client.id)

        # Убеждаемся, что последний автор — наш api_user.id
        assert history[0]["pgh_context"]["user"] == str(api_user.id)

    async def test_system_api_audit_logs_system_uuid(self, system_client: AsyncClient):
        """Проверка: системный запрос записывает SYSTEM_USER_ID в историю."""
        payload: dict[str, Any] = {
            "name": "System Corp",
            "unp": "191111111",  # Валидный тестовый УНП
            "org_type": "ooo",
            "tax_system": "usn_no_nds",
            "status": "active",
        }

        # Создаем клиента через систему
        response = await system_client.post("/api/clients/", data=payload, content_type="application/json")
        assert response.status_code == 201
        client_id = response.json()["id"]

        # Проверяем историю в БД напрямую (что в pghistory записался SYSTEM_USER_ID)
        from apps.audit.selectors import get_client_history_queryset

        history = await get_client_history_queryset(client_id)

        # В контексте pghistory должен быть  системный UUID
        last_event = history[0]

        # Убеждаемся, что pghistory зафиксировала SYSTEM_USER_ID
        assert str(last_event["pgh_context"]["user"]) == str(SYSTEM_USER_ID)

    async def test_initiator_logging_with_details(self, system_client: AsyncClient, settings):
        """Проверка: лог инициатора запроса к API содержит User-Agent, если флаг включен."""
        settings.LOG_DETAILED_AUDIT = True

        # Создаем клиента
        client = await sync_to_async(ClientFactory)()

        # Делаем изменение через API
        patch_data = {"name": "Updated Name"}

        # Обновляем клиента от имени системного юзера с кастомным User-Agent
        test_user_agent = "Test-System/1.0"
        headers = {"HTTP_USER_AGENT": test_user_agent}
        await system_client.patch(
            f"/api/clients/{client.id}",
            data=patch_data,
            content_type="application/json",
            **headers,
        )

        # Запрашиваем историю от имени системного юзера
        start = perf_counter()
        history = await system_client.get(f"{self.endpoint}{client.id}")
        elapsed_time = perf_counter() - start

        # --- Проверки ---

        # Статус код
        await self.assert_status(response=history, expected_status=200)

        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=300)

        data = history.json()

        # Валидация схемы
        await self.validate_schema(data=data, schema=ClientHistoryOut, many=True)

        update_event = next(event for event in data if event["pgh_label"] == "update")
        assert len(data) >= 1
        assert update_event["user_agent"] == test_user_agent
