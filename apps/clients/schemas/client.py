"""
Схемы данных (DTO) для Клиентов.
"""

import uuid
from datetime import datetime

from ninja import Schema
from pydantic import EmailStr, Field, field_validator

from apps.clients.models import ClientStatus, OrganizationType, TaxSystem
from apps.common.validators import validate_phone_pydantic
from apps.users.schemas import DepartmentOut, UserOut


class ContactPersonSchema(Schema):
    """
    Структурированные данные контактного лица клиента.
    """

    role: str = Field(..., description="Должность (например: Директор, ИП)")

    # Regex паттерн для проверки имен (только буквы, пробелы, дефисы)
    full_name: str = Field(
        ...,
        min_length=2,
        max_length=150,
        pattern=r"^[а-яА-ЯёЁa-zA-Z\s-]+$",
        description="ФИО",
    )

    email: EmailStr | None = Field(None, description="Email")
    phone: str | None = Field(None, description="Мобильный телефон")

    @field_validator("phone")
    @classmethod
    def validate_phone_field(cls, phone: str | None) -> str | None:
        """Проверяет формат телефона через phonenumbers."""
        validate_phone_pydantic(phone)


class ClientContactInfo(Schema):
    """
    Общая структура контактных данных клиента.
    """

    general_email: EmailStr | None = Field(None, description="Email организации")
    general_phone: str | None = Field(None, description="Телефон организации")
    address_legal: str | None = Field(None, description="Юридический адрес")
    address_mailing: str | None = Field(None, description="Почтовый адрес")
    website: str | None = Field(None, description="Сайт компании")

    # Список контактных лиц
    contacts: list[ContactPersonSchema] = Field(default_factory=list, description="Список контактных лиц")

    @field_validator("general_phone")
    @classmethod
    def validate_phone_field(cls, phone: str | None) -> str | None:
        """Проверяет формат телефона через phonenumbers."""
        return validate_phone_pydantic(phone)


class ClientCreate(Schema):
    """
    Схема для создания нового клиента (входные данные).
    """

    name: str = Field(..., min_length=1, max_length=150, description="Краткое название")
    full_legal_name: str | None = Field(None, max_length=255, description="Полное юридическое название")

    # Regex паттерн проверяет, что это ровно 9 цифр
    unp: str = Field(..., pattern=r"^\d{9}$", description="УНП (9 цифр)")

    org_type: OrganizationType = Field(default=OrganizationType.OOO, description="Тип организации")
    tax_system: TaxSystem = Field(default=TaxSystem.USN_NO_NDS, description="Налоговый режим")
    status: ClientStatus = Field(default=ClientStatus.ONBOARDING, description="Статус клиента")

    # Обслуживающий отдел
    department_id: uuid.UUID | None = Field(None, description="ID обслуживающего отдела")

    # Ответственные
    accountant_id: uuid.UUID | None = Field(None, description="ID Ведущего бухгалтера")
    primary_accountant_id: uuid.UUID | None = Field(None, description="ID Бухгалтера по первичной документации")
    payroll_accountant_id: uuid.UUID | None = Field(None, description="ID Бухгалтера по заработной плате")
    hr_specialist_id: uuid.UUID | None = Field(None, description="ID Специалиста по кадрам")

    # Вложенная схема для контактов
    # Фронтенд будет слать JSON: {"contact_info": {"contacts": [{"role": "Директор", ...}]}}
    contact_info: ClientContactInfo = Field(
        default_factory=ClientContactInfo,
        description="Контактная информация и список лиц",
    )

    # Интеграции
    google_folder_id: str | None = Field(None, max_length=100, description="ID папки на Google Drive")


class ClientOut(Schema):
    """
    Схема для вывода данных о клиенте (ответ API).
    """

    id: uuid.UUID = Field(..., description="Уникальный идентификатор клиента")

    # Enum поля автоматически сериализуются в строки (значения)
    status: ClientStatus = Field(..., description="Текущий статус")
    org_type: OrganizationType
    tax_system: TaxSystem

    name: str
    full_legal_name: str | None = None
    unp: str

    # Вложенные объекты (Nested objects)
    department: DepartmentOut | None = Field(None, description="Обслуживающий отдел")
    accountant: UserOut | None = Field(None, description="Ведущий бухгалтер")
    primary_accountant: UserOut | None = Field(None, description="Бухгалтер по первичной документации")
    payroll_accountant: UserOut | None = Field(None, description="Бухгалтер по заработной плате")
    hr_specialist: UserOut | None = Field(None, description="Специалист по кадрам")

    contact_info: ClientContactInfo | None = None
    google_folder_id: str | None = None

    created_at: datetime
    updated_at: datetime

    # Config для Pydantic v2, чтобы он умел брать данные из ORM объектов
    # (в Ninja Schema это обычно включено по умолчанию, но для явности)
    # model_config = {"from_attributes": True}
