"""
Схемы данных (DTO) для Клиентов.
"""

from datetime import datetime
from uuid import UUID

from ninja import Schema
from pydantic import ConfigDict, Field

from apps.clients.models import ClientStatus, OrganizationType, TaxSystem
from apps.clients.schemas.contacts import ClientContactInfo, ClientContactInfoUpdate
from apps.users.schemas import DepartmentOut, UserOut


class ClientCreate(Schema):
    """
    Схема для создания нового клиента (входные данные).
    """

    model_config = ConfigDict(
        extra="forbid",  # Запрет лишних полей (защита от опечаток фронта)
        str_strip_whitespace=True,  # Автоматически убирать лишние пробелы в начале/конце строк
    )

    name: str = Field(..., min_length=1, max_length=150, description="Краткое название")
    full_legal_name: str | None = Field(default=None, max_length=255, description="Полное юридическое название")

    # Regex паттерн проверяет, что это ровно 9 цифр
    unp: str = Field(..., pattern=r"^\d{9}$", description="УНП")

    org_type: OrganizationType = Field(default=OrganizationType.OOO, description="Тип организации")
    tax_system: TaxSystem = Field(default=TaxSystem.USN_NO_NDS, description="Система налогообложения")
    status: ClientStatus = Field(default=ClientStatus.ONBOARDING, description="Статус клиента")

    # Обслуживающий отдел
    department_id: UUID | None = Field(default=None, description="ID обслуживающего отдела")

    # Ответственные
    accountant_id: UUID | None = Field(default=None, description="ID Ведущего бухгалтера")
    primary_accountant_id: UUID | None = Field(default=None, description="ID Бухгалтера по первичной документации")
    payroll_accountant_id: UUID | None = Field(default=None, description="ID Бухгалтера по заработной плате")
    hr_specialist_id: UUID | None = Field(default=None, description="ID Специалиста по кадрам")

    # Вложенная схема для контактов
    # Фронтенд будет слать JSON: {"contact_info": {"contacts": [{"role": "Директор", ...}]}}
    contact_info: ClientContactInfo = Field(
        default_factory=ClientContactInfo,
        description="Контактная информация",
    )

    # Интеграции
    google_folder_id: str | None = Field(default=None, max_length=100, description="ID папки на Google Drive")


class ClientUpdate(Schema):
    """
    Схема для частичного обновления клиента (PATCH).
    Все поля опциональны. При передаче null значение очищается.
    """

    model_config = ConfigDict(
        extra="forbid",  # Запрет лишних полей (защита от опечаток фронта)
        str_strip_whitespace=True,  # Автоматически убирать лишние пробелы в начале/конце строк
    )

    name: str | None = Field(default=None, min_length=1, max_length=150, description="Обновить краткое название")
    full_legal_name: str | None = Field(default=None, max_length=255, description="Обновить полное юр. название")

    # Regex паттерн проверяет, что это ровно 9 цифр
    unp: str | None = Field(default=None, pattern=r"^\d{9}$", description="Обновить УНП")

    org_type: OrganizationType | None = Field(default=None, description="Обновить тип организации")
    tax_system: TaxSystem | None = Field(default=None, description="Обновить систему налогообложения")
    status: ClientStatus | None = Field(default=None, description="Обновить статус клиента")

    # Обслуживающий отдел
    department_id: UUID | None = Field(default=None, description="Обновить ID обслуживающего отдела")

    # Ответственные
    accountant_id: UUID | None = Field(
        default=None,
        description="Обновить ID Ведущего бухгалтера",
    )
    primary_accountant_id: UUID | None = Field(
        default=None,
        description="Обновить ID Бухгалтера по первичной документации",
    )
    payroll_accountant_id: UUID | None = Field(
        default=None,
        description="Обновить ID Бухгалтера по заработной плате",
    )
    hr_specialist_id: UUID | None = Field(
        default=None,
        description="Обновить ID Специалиста по кадрам",
    )

    # Вложенная схема для PATCH (позволяет обновлять email, не трогая телефон)
    contact_info: ClientContactInfoUpdate | None = Field(
        default=None,
        description="Обновить контактную информацию",
    )

    # Интеграции
    google_folder_id: str | None = Field(default=None, max_length=100, description="Обновить ID папки на Google Drive")


class ClientOut(Schema):
    """
    Схема для вывода данных о клиенте (ответ API).
    """

    # Брать данные из ORM объектов (в Ninja Schema включено по умолчанию)
    # model_config = ConfigDict(from_attributes=True)

    id: UUID = Field(..., description="Уникальный идентификатор клиента (UUIDv7)")

    # Enum поля автоматически сериализуются в строки (значения)
    status: ClientStatus = Field(..., description="Текущий статус")
    org_type: OrganizationType = Field(..., description="Тип организации")
    tax_system: TaxSystem = Field(..., description="Система налогообложения")

    name: str = Field(..., description="Краткое название")
    full_legal_name: str | None = Field(default=None, description="Полное юридическое название")
    unp: str = Field(..., description="УНП")

    # Вложенные объекты (Nested objects)
    department: DepartmentOut | None = Field(default=None, description="Обслуживающий отдел")
    accountant: UserOut | None = Field(default=None, description="Ведущий бухгалтер")
    primary_accountant: UserOut | None = Field(default=None, description="Бухгалтер по первичной документации")
    payroll_accountant: UserOut | None = Field(default=None, description="Бухгалтер по заработной плате")
    hr_specialist: UserOut | None = Field(default=None, description="Специалист по кадрам")

    contact_info: ClientContactInfo | None = Field(default=None, description="Структурированные контактные данные")
    google_folder_id: str | None = Field(default=None, description="ID папки Google Drive")

    created_at: datetime = Field(..., description="Дата и время создания клиента")
    updated_at: datetime = Field(..., description="Дата и время последнего изменения клиента")
