"""
Схемы для отображения истории изменений (журнала аудита).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from ninja import Field, Schema

from apps.clients.models import ClientStatus, OrganizationType, TaxSystem


class HistoryContextSchema(Schema):
    """
    Схема контекста изменения.
    Данные берутся из pghistory.Context.
    """

    # В metadata: user=user_id
    metadata: dict[str, Any] = Field(..., description="Метаданные контекста (ID пользователя)")


class ClientHistoryOut(Schema):
    """
    Схема одной записи в истории изменений клиента.
    Отображает состояние объекта (Snapshot) на момент времени.
    """

    # Системные поля pghistory
    pgh_id: int = Field(..., description="ID записи истории")
    pgh_created_at: datetime = Field(..., description="Дата и время изменения")
    pgh_label: str = Field(..., description="Метка события (snapshot, insert, update)")

    # Нельзя select_related для User внутри JSON-метаданных в pghistory, поэтому отдаем контекст как есть
    # Фронтенд сможет сопоставить ID юзера со своим кэшем пользователей
    # или можно обогатить данные в сервисе (но это сложнее для async списка)
    pgh_context: HistoryContextSchema | None = Field(None, description="Контекст изменения")

    # Поля снимка (состояние клиента)
    id: UUID
    name: str
    full_legal_name: str
    unp: str
    status: ClientStatus
    org_type: OrganizationType
    tax_system: TaxSystem
