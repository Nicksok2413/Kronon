"""
Селекторы (Read Logic) для приложения Audit.

Отвечают за получение данных из БД.
Используют асинхронный подход для неблокирующего ввода-вывода.
"""

from typing import Any
from uuid import UUID

import pghistory.models


async def get_client_history_queryset(client_id: UUID) -> list[dict[str, Any]]:
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
        # Берем только нужные поля
        .only(
            "pgh_id",
            "pgh_created_at",
            "pgh_label",
            "pgh_diff",
            "pgh_context",
            "pgh_data",
        )
        .order_by("-pgh_created_at")
    )

    events_data = []

    # Итерируемся асинхронно
    async for event in events_queryset:
        # Собираем контекст
        context_data = event.pgh_context or {}  # pgh_context - JSON поле с денормализованным контекстом

        # Собираем словарь, который Pydantic превратит в схему ClientSnapshot
        snapshot_data = event.pgh_data or {}  # pgh_data - JSON поле со снэпшотом модели

        # Собираем полный словарь событий
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

    # Возвращаем список словарей событий
    return events_data
