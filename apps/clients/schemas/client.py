"""
Схемы данных (DTO) для Клиентов.
"""

import uuid
from datetime import datetime

from ninja import Schema
from pydantic import ConfigDict, EmailStr, Field

from apps.clients.models import ClientStatus, OrganizationType, TaxSystem
from apps.common.types import PhoneNumber
from apps.users.schemas import DepartmentOut, UserOut


class ContactPersonSchema(Schema):
    """
    Структурированные данные контактного лица клиента.
    """

    role: str | None = Field(default=None, description="Должность (например: Директор, ИП)")

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
        # Regex паттерн для проверки имен (только буквы, пробелы, дефисы)
        pattern=r"^[а-яА-ЯёЁa-zA-Z\s-]+$",
        description="ФИО",
    )

    email: EmailStr | None = Field(default=None, description="Email")
    phone: PhoneNumber | None = Field(default=None, description="Мобильный телефон")


class ClientContactInfo(Schema):
    """
    Общая структура контактных данных клиента.
    """

    general_email: EmailStr | None = Field(default=None, description="Email организации")
    general_phone: PhoneNumber | None = Field(default=None, description="Телефон организации")
    address_legal: str | None = Field(default=None, description="Юридический адрес")
    address_mailing: str | None = Field(default=None, description="Почтовый адрес")
    website: str | None = Field(default=None, description="Сайт компании")

    # Список контактных лиц
    contacts: list[ContactPersonSchema] = Field(default_factory=list, description="Список контактных лиц")


class ClientContactInfoUpdate(Schema):
    """
    Схема для частичного обновления контактов.
    """

    general_email: EmailStr | None = None
    general_phone: PhoneNumber | None = None
    address_legal: str | None = None
    address_mailing: str | None = None
    website: str | None = None

    # Списком управляем целиком: если прислали новый список - заменяем старый
    # Если нужно будет менять контакты точечно, будем делать через отдельные эндпоинты
    # /api/clients/{id}/contacts/{contact_id}, иначе логика слияния списков превратится в ад
    contacts: list[ContactPersonSchema] | None = None


class ClientCreate(Schema):
    """
    Схема для создания нового клиента (входные данные).
    """

    model_config = ConfigDict(
        extra="forbid",  # Запрет лишних полей (защита от опечаток фронта)
        str_strip_whitespace=True,  # Автоматически убирать лишние пробелы в начале/конце строк
        validate_assignment=True,  # Валидация при изменении атрибутов после создания объекта
    )

    name: str = Field(..., min_length=1, max_length=150, description="Краткое название")
    full_legal_name: str | None = Field(default=None, max_length=255, description="Полное юридическое название")
    unp: str = Field(..., pattern=r"^\d{9}$", description="УНП")  # Regex паттерн проверяет, что это ровно 9 цифр

    org_type: OrganizationType = Field(default=OrganizationType.OOO, description="Тип организации")
    tax_system: TaxSystem = Field(default=TaxSystem.USN_NO_NDS, description="Налоговый режим")
    status: ClientStatus = Field(default=ClientStatus.ONBOARDING, description="Статус клиента")

    # Обслуживающий отдел
    department_id: uuid.UUID | None = Field(default=None, description="ID обслуживающего отдела")

    # Ответственные
    accountant_id: uuid.UUID | None = Field(default=None, description="ID Ведущего бухгалтера")
    primary_accountant_id: uuid.UUID | None = Field(default=None, description="ID Бухгалтера по первичной документации")
    payroll_accountant_id: uuid.UUID | None = Field(default=None, description="ID Бухгалтера по заработной плате")
    hr_specialist_id: uuid.UUID | None = Field(default=None, description="ID Специалиста по кадрам")

    # Вложенная схема для контактов
    # Фронтенд будет слать JSON: {"contact_info": {"contacts": [{"role": "Директор", ...}]}}
    contact_info: ClientContactInfo = Field(
        default_factory=ClientContactInfo,
        description="Контактная информация и список лиц",
    )

    # Интеграции
    google_folder_id: str | None = Field(default=None, max_length=100, description="ID папки на Google Drive")


class ClientUpdate(Schema):
    """
    Схема для частичного обновления клиента (PATCH).
    """

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
    )

    name: str | None = Field(default=None, min_length=1, max_length=150)
    full_legal_name: str | None = Field(default=None, max_length=255)
    unp: str | None = Field(default=None, pattern=r"^\d{9}$")

    org_type: OrganizationType | None = None
    tax_system: TaxSystem | None = None
    status: ClientStatus | None = None

    department_id: uuid.UUID | None = None

    accountant_id: uuid.UUID | None = None
    primary_accountant_id: uuid.UUID | None = None
    payroll_accountant_id: uuid.UUID | None = None
    hr_specialist_id: uuid.UUID | None = None

    # Вложенная схема тоже для апдейта
    contact_info: ClientContactInfoUpdate | None = None

    google_folder_id: str | None = Field(default=None, max_length=100)


class ClientOut(Schema):
    """
    Схема для вывода данных о клиенте (ответ API).
    """

    # Брать данные из ORM объектов (в Ninja Schema включено по умолчанию)
    # model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID = Field(..., description="Уникальный идентификатор клиента (UUIDv7)")

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
