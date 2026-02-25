"""
Схемы для отображения истории изменений (журнала аудита).
"""

from datetime import datetime
from typing import Any

from ninja import Field, Schema


class HistoryContext(Schema):
    """Метаданные из pgh_context"""

    user_email: str | None = None
    app_source: str | None = None
    ip: str | None = None
    method: str | None = None


class ClientHistoryItem(Schema):
    """
    Схема одной записи в истории изменений клиента.
    Отображает состояние объекта (Snapshot) на момент времени.
    """

    # Системные поля pghistory
    pgh_id: int = Field(..., description="ID записи истории")
    pgh_created_at: datetime = Field(..., description="Дата и время изменения")
    pgh_label: str = Field(..., description="Метка события (snapshot, insert, update)")

    # Разница изменений (автоматически считается базой)
    # Пример: {"status": ["old", "new"], "name": ["OldName", "NewName"]}
    pgh_diff: dict[str, list[Any]] | None = Field(None, description="Разница изменений (Old -> New)")

    # Контекст
    pgh_context: HistoryContext | None = Field(None, description="Контекст изменения")

    # Snapshot данных (pgh_data хранит все поля модели на момент изменения)
    pgh_data: dict[str, Any]
