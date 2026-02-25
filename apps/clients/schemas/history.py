"""
Схемы для отображения истории изменений (журнала аудита).
"""

from datetime import datetime
from typing import Any

from ninja import Field, Schema


class HistoryContextMetadata(Schema):
    """
    Метаданные контекста из pgh_context.
    """

    user: str | None = Field(default=None, description="ID пользователя")
    user_email: str | None = Field(default=None, description="Email пользователя")
    app_source: str | None = Field(default=None, description="Источник изменения (API, Celery, CLI)")
    ip_address: str | None = Field(default=None, description="IP адрес инициатора")
    method: str | None = Field(default=None, description="HTTP метод")
    url: str | None = Field(default=None, description="URL запроса")
    celery_task: str | None = Field(default=None, description="Имя задачи Celery")
    command: str | None = Field(default=None, description="Команда CLI")


class HistoryContextOut(Schema):
    """Обертка контекста."""

    metadata: HistoryContextMetadata = Field(..., description="Метаданные события")


class ClientHistoryOut(Schema):
    """
    Схема одной записи в истории изменений клиента.
    Включает Snapshot данных, Diff и Context.
    """

    # Системные поля pghistory
    pgh_id: int = Field(..., description="ID события")
    pgh_created_at: datetime = Field(..., description="Дата и время изменения")
    pgh_label: str = Field(..., description="Тип события (snapshot, insert, update)")

    # Разница изменений (автоматически считается базой)
    # Пример: {"status": ["old", "new"], "name": ["OldName", "NewName"]}
    pgh_diff: dict[str, list[Any]] | None = Field(None, description="Разница изменений (Old -> New)")

    # Контекст
    pgh_context: HistoryContextOut | None = Field(None, description="Контекст изменения")

    # Snapshot данных (pgh_data хранит все поля модели на момент после изменения)
    pgh_data: dict[str, Any]
