"""
Схемы данных (DTO) для Пользователей и Отделов.
"""

from uuid import UUID

from ninja import Schema
from pydantic import EmailStr, Field

from apps.users.models import UserRole


class DepartmentOut(Schema):
    """
    Схема вывода информации об отделе (краткая).
    """

    id: UUID = Field(..., description="Уникальный идентификатор отдела (UUIDv7)")
    name: str = Field(..., description="Название отдела")


class UserOut(Schema):
    """
    Схема вывода информации о сотруднике (краткая).
    Используется для отображения ответственных лиц.
    """

    id: UUID = Field(..., description="Уникальный идентификатор сотрудника (UUIDv7)")
    email: EmailStr = Field(..., description="Email сотрудника")
    last_name: str | None = Field(default=None, description="Фамилия сотрудника")
    first_name: str | None = Field(default=None, description="Имя сотрудника")
    middle_name: str | None = Field(default=None, description="Отчество сотрудника")
    role: UserRole = Field(..., description="Роль сотрудника")

    # Вычисляемое поле (Computed Field)
    # Ninja/Pydantic умеет вызывать методы модели, если имя совпадает
    full_name_rus: str | None = Field(default=None, description="ФИО сотрудника")
