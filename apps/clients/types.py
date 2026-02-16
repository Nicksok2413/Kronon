"""
Доменные типы и структуры данных (Value Objects) приложения Clients.

Описывают структуру данных, хранящихся внутри JSON-полей.
Не зависят от API и Ninja.
"""

from pydantic import BaseModel as PydanticBaseModel
from pydantic import EmailStr, Field

from apps.common.types import PhoneNumber


class ContactPerson(PydanticBaseModel):
    """
    Структура контактного лица (внутри JSON).
    Используем pydantic BaseModel, так как это не Schema для Ninja, а внутренняя структура.
    """

    role: str | None = Field(default=None, description="Должность (например: Директор, ИП)")

    full_name: str | None = Field(
        default=None,
        min_length=2,
        max_length=150,
        # Regex паттерн для проверки имен (только буквы, пробелы, дефисы)
        pattern=r"^[а-яА-ЯёЁa-zA-Z\s-]+$",
        description="ФИО контактного лица",
    )

    email: EmailStr | None = Field(default=None, description="Контактный Email")
    phone: PhoneNumber | None = Field(default=None, description="Мобильный телефон")


class ContactInfo(PydanticBaseModel):
    """
    Структура хранения контактов в БД (Value Object).
    Используем pydantic BaseModel, так как это не Schema для Ninja, а внутренняя структура.
    """

    general_email: EmailStr | None = Field(default=None, description="Email организации")
    general_phone: PhoneNumber | None = Field(default=None, description="Телефон организации")
    address_legal: str | None = Field(default=None, description="Юридический адрес")
    address_mailing: str | None = Field(default=None, description="Почтовый адрес (для корреспонденции)")
    website: str | None = Field(default=None, description="Веб-сайт организации")

    # Список контактных лиц
    contacts: list[ContactPerson] = Field(default_factory=list, description="Список контактных лиц")
