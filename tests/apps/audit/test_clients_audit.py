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

    async def test_history_initiator_sync(self, admin_client: AsyncClient, admin_user: Any):
        """Проверка записи ID пользователя, изменившего клиента."""
        # Создаем клиента
        client = await sync_to_async(ClientFactory)()

        # Патчим клиента от имени админа
        patch_data = {"name": "Updated Name"}
        await admin_client.patch(f"/api/clients/{client.id}", data=patch_data, content_type="application/json")

        # Проверяем историю в БД напрямую (что в pghistory записался admin_user.id)
        from apps.audit.selectors import get_client_history_queryset

        history = await get_client_history_queryset(client.id)

        # Проверяем, что в контексте зафиксирован ID админа
        assert str(history[0]["pgh_context"]["user"]) == str(admin_user.id)

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

        # Проверяем, что в контексте зафиксирован SYSTEM_USER_ID
        assert str(history[0]["pgh_context"]["user"]) == str(SYSTEM_USER_ID)

    async def test_initiator_logging_with_details(self, system_client: AsyncClient, settings):
        """Проверка: лог инициатора запроса к API содержит User-Agent, если флаг включен."""
        # Включаем флаг
        settings.LOG_DETAILED_AUDIT = True

        # Создаем клиента
        client = await sync_to_async(ClientFactory)()

        # Патчим клиента от имени системного юзера с кастомным User-Agent
        patch_data = {"name": "Updated Name"}
        test_user_agent = "Test-System/1.0"
        await system_client.patch(
            f"/api/clients/{client.id}",
            data=patch_data,
            content_type="application/json",
            headers={"user-agent": test_user_agent},
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
        assert len(data) >= 1

        # Валидация схемы
        await self.validate_schema(data=data, schema=ClientHistoryOut, many=True)

        # Получаем событие 'update'
        update_event = next(event for event in data if event["pgh_label"] == "update")

        # Проверяем, что в контексте зафиксирован кастомный User-Agent
        assert update_event["pgh_context"]["user_agent"] == test_user_agent

    async def test_history_diff_content(self, admin_client: AsyncClient, api_user: Any) -> None:
        """
        Проверка содержимого pgh_diff: изменение ответственного бухгалтера.
        """
        # Создаем клиента без бухгалтера
        client = await sync_to_async(ClientFactory)(accountant=None)

        # Назначаем бухгалтера (api_user) через патч от имени админа
        patch_data = {"accountant_id": str(api_user.id)}
        await admin_client.patch(f"/api/clients/{client.id}", data=patch_data, content_type="application/json")

        # Запрашиваем историю от имени админа
        history_response = await admin_client.get(f"{self.endpoint}{client.id}")
        data = history_response.json()

        # Получаем событие 'update'
        update_event = next(event for event in data if event["pgh_label"] == "update")
        diff = update_event["pgh_diff"]

        # Проверяем, что поле accountant_id изменилось
        assert "accountant_id" in diff
        # Diff - массив [old_value, new_value]
        # Так как изначально accountant был None, старое значение должно быть None
        assert diff["accountant_id"][0] is None
        # Новое значение должно быть равно ID нашего бухгалтера
        assert diff["accountant_id"][1] == str(api_user.id)
