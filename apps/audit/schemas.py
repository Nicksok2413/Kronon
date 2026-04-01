"""
Схемы для отображения истории изменений (журнала аудита).
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from ninja import Field, Schema

from apps.clients.models import ClientStatus, OrganizationType, TaxSystem


class HistoryContextData(Schema):
    """
    Данные контекста из pgh_context.
    """

    user: str | None = Field(default=None, description="ID пользователя")
    user_email: str | None = Field(default=None, description="Email пользователя")
    correlation_id: str | None = Field(default=None, description="ID корреляции")
    ip_address: str | None = Field(default=None, description="IP адрес инициатора")
    user_agent: str | None = Field(default=None, description="User-Agent инициатора")
    url: str | None = Field(default=None, description="URL запроса")
    method: str | None = Field(default=None, description="HTTP метод")
    service: str | None = Field(default=None, description="Сервис - источник изменения объекта (API, Celery, CLI)")
    celery_task_name: str | None = Field(default=None, description="Название Celery-задачи")
    celery_task_id: str | None = Field(default=None, description="ID Celery-задачи")
    cli_command: str | None = Field(default=None, description="CLI команда")


class ClientSnapshot(Schema):
    """
    Снэпшот данных клиента (raw data from DB).
    В истории хранятся ID связей, а не развернутые объекты.
    """

    # Основные поля
    id: UUID = Field(..., description="ID клиента")
    name: str = Field(..., description="Краткое название")
    full_legal_name: str | None = Field(default=None, description="Полное юридическое название")
    unp: str = Field(..., description="УНП")
    status: ClientStatus = Field(..., description="Статус клиента")
    org_type: OrganizationType = Field(..., description="Тип организации")
    tax_system: TaxSystem = Field(..., description="Система налогообложения")

    # Связи (хранятся как UUID)
    department_id: UUID | None = Field(default=None, description="ID обслуживающего отдела")
    accountant_id: UUID | None = Field(default=None, description="ID ведущего бухгалтера")
    primary_accountant_id: UUID | None = Field(default=None, description="ID бухгалтера по первичной документации")
    payroll_accountant_id: UUID | None = Field(default=None, description="ID бухгалтера по заработной плате")
    hr_specialist_id: UUID | None = Field(default=None, description="ID специалиста по кадрам")

    # JSON поле
    contact_info: dict[str, Any] = Field(default_factory=dict, description="Контактная информация")

    # Интеграции
    google_folder_id: str | None = Field(default=None, description="ID папки на Google Drive")

    # Таймстэмпы
    created_at: datetime = Field(..., description="Дата создания записи")
    updated_at: datetime = Field(..., description="Дата последнего обновления записи")
    deleted_at: datetime | None = Field(default=None, description="Дата мягкого удаления (если удален)")


class ClientHistoryOut(Schema):
    """
    Схема одной записи в истории изменений клиента (ответ API).
    Включает Snapshot данных, Diff и Context.
    """

    # Системные поля pghistory
    pgh_id: int = Field(..., description="ID события")
    pgh_created_at: datetime = Field(..., description="Дата и время изменения")
    pgh_label: str = Field(..., description="Тип события (insert, update, delete)")

    # Разница изменений (автоматически считается базой)
    # Пример: {"status": ["old", "new"], "name": ["OldName", "NewName"]}
    pgh_diff: dict[str, list[Any]] | None = Field(default=None, description="Разница изменений (Old -> New)")

    # Контекст
    pgh_context: HistoryContextData | None = Field(default=None, description="Денормализованный контекст")

    # Snapshot данных (вложенная схема)
    snapshot: ClientSnapshot = Field(..., description="Состояние объекта после изменения")
