"""
Схемы данных (DTO) для Клиентов.
"""

import uuid
from datetime import datetime

from ninja import Schema

from apps.clients.models import ClientStatus, OrganizationType, TaxSystem


class ClientOut(Schema):
    """
    Схема для вывода данных о клиенте.
    """

    id: uuid.UUID

    # Enum поля автоматически сериализуются в строки (значения)
    status: ClientStatus
    org_type: OrganizationType
    tax_system: TaxSystem

    name: str
    full_legal_name: str | None = None
    unp: str

    # Вложенные объекты (User) пока выведем просто ID или строкой,
    # чтобы не усложнять схему прямо сейчас. Позже сделаем UserOut
    accountant_id: uuid.UUID | None = None

    created_at: datetime
    updated_at: datetime

    # Config для Pydantic v2, чтобы он умел брать данные из ORM объектов
    # (в Ninja Schema это обычно включено по умолчанию, но для явности)
    # model_config = {"from_attributes": True}
