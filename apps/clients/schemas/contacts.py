"""
Схемы данных (DTO) для контактной информации.
"""

from ninja import Schema
from pydantic import EmailStr, Field

from apps.clients.types import ContactInfo, ContactPerson
from apps.common.types import PhoneNumber


# Наследуем Schema (Ninja) от BaseModel (Pydantic), они совместимы
class ContactPersonSchema(ContactPerson, Schema):
    """
    DTO для контактного лица клиента (внутри JSON поля).
    """

    pass


# Наследуем Schema (Ninja) от BaseModel (Pydantic), они совместимы
class ClientContactInfo(ContactInfo, Schema):
    """
    DTO для контактных данных клиента (JSON поле в БД).
    """

    pass


class ClientContactInfoUpdate(Schema):
    """
    Схема для частичного обновления контактов (все поля опциональны).
    Используется в PATCH запросах.
    """

    general_email: EmailStr | None = Field(default=None, description="Обновить Email организации")
    general_phone: PhoneNumber | None = Field(default=None, description="Обновить телефон организации")
    address_legal: str | None = Field(default=None, description="Обновить юридический адрес организации")
    address_mailing: str | None = Field(default=None, description="Обновить почтовый адрес организации")
    website: str | None = Field(default=None, description="Обновить Веб-сайт организации")

    # Списком управляем целиком: если прислали новый список - заменяем старый
    # Если нужно будет менять контакты точечно, будем делать через отдельные эндпоинты
    # /api/clients/{id}/contacts/{contact_id}, иначе логика слияния списков превратится в ад
    contacts: list[ContactPersonSchema] | None = Field(
        default=None, description="Полный список контактных лиц (заменяет текущий)"
    )
