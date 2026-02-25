"""
Селекторы (Read Logic) для приложения Clients.

Отвечают за получение данных из БД.
Используют асинхронный подход для неблокирующего ввода-вывода.
"""

from typing import Any
from uuid import UUID

import pghistory.models
from loguru import logger as log

from apps.clients.models import Client
from apps.common.managers import SoftDeleteQuerySet


def get_client_queryset() -> SoftDeleteQuerySet[Client]:
    """
    Возвращает базовый QuerySet для списка клиентов с оптимизацией.

    Применяет `select_related` для всех связанных полей, необходимых в API,
    чтобы избежать проблемы N+1 запросов.
    Гарантирует сортировку по ID (в обратном порядке).

    Returns:
        SoftDeleteQuerySet[Client]: Оптимизированный QuerySet.
    """
    # Логируем на уровне DEBUG, так как это частая операция
    log.debug("Building base client queryset with select_related")

    return (
        Client.objects.active()
        .select_related(
            "department",
            "accountant",
            "primary_accountant",
            "payroll_accountant",
            "hr_specialist",
        )
        .order_by("-id")
    )  # Гарантируем сортировку


async def get_client_by_id(client_id: UUID) -> Client | None:
    """
    Асинхронно получает детальную информацию о клиенте по ID.

    Использует оптимизированный QuerySet.

    Args:
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Returns:
        Client | None: Объект клиента или None, если не найден/удален.
    """
    log.debug(f"Fetching client. ID: {client_id}")

    try:
        # .afirst() вместо .aget(), чтобы избежать исключения DoesNotExist и вернуть None
        client = await get_client_queryset().filter(id=client_id).afirst()

        if client:
            log.debug(f"Client found: name: {client.name}, UNP: {client.unp}")
        else:
            log.warning(f"Client not found or deleted. ID: {client_id}")

        return client

    except Exception as exc:
        log.error(f"DB Error while fetching client. ID: {client_id}: {exc}")
        # Глобальный хендлер превратит это в 500
        raise


async def get_client_history_list(client_id: UUID) -> list[dict[str, Any]]:
    """
    Получает агрегированную историю изменений клиента с вычисленными диффами.

    Использует глобальную модель `pghistory.models.Events` для доступа к `pgh_diff`.

    Args:
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Returns:
        list[dict[str, Any]]: Список словарей событий, готовых для сериализации в ClientHistoryOut.
    """
    # Используем глобальную модель Events, фильтруем вручную по модели и ID
    # tracks() работает с объектами, а у нас ID + async, проще фильтровать сырым образом

    events_queryset = (
        pghistory.models.Events.objects.filter(
            pgh_obj_model="clients.Client",
            pgh_obj_id=client_id,
        )
        .select_related("pgh_context")
        .order_by("-pgh_created_at")
    )

    events_data = []

    # Итерируемся асинхронно
    async for event in events_queryset:
        # Собираем контекст
        context_data = None

        if event.pgh_context:
            context_data = {"metadata": event.pgh_context.metadata}

        # Собираем словарь, который Pydantic превратит в схему ClientSnapshot
        snapshot_data = event.pgh_data or {}  # pgh_data - JSON поле со снэпшотом модели

        events_data.append(
            {
                "pgh_id": event.pgh_id,
                "pgh_created_at": event.pgh_created_at,
                "pgh_label": event.pgh_label,
                "pgh_diff": event.pgh_diff,
                "pgh_context": context_data,
                "snapshot": snapshot_data,
            }
        )

    return events_data
