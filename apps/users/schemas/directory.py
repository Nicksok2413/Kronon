"""
Публичные схемы данных (DTO) для Справочника сотрудников (Directory).
Не содержат чувствительной HR-информации.
"""

from uuid import UUID

from ninja import Field, Schema

from apps.users.models import User, UserRole


class DepartmentDirectoryOut(Schema):
    """
    Схема отдела для публичного справочника.
    """

    id: UUID = Field(..., description="ID отдела (UUIDv7)")
    name: str = Field(..., description="Название отдела")


class UserDirectoryOut(Schema):
    """
    Схема сотрудника для публичного справочника.
    Доступна всем авторизованным пользователям системы.
    """

    id: UUID = Field(..., description="ID сотрудника (UUIDv7)")
    email: str = Field(..., description="Рабочий email")
    last_name: str | None = Field(default=None, description="Фамилия")
    first_name: str | None = Field(default=None, description="Имя")
    middle_name: str | None = Field(default=None, description="Отчество")

    # Вычисляемое поле из модели (computed property)
    # Ninja/Pydantic умеет вызывать методы модели, если имя совпадает
    full_name_rus: str | None = Field(default=None, description="ФИО сотрудника")

    role: UserRole = Field(..., description="Должность / Роль")

    # Вложенная схема
    department: DepartmentDirectoryOut | None = Field(default=None, description="Отдел")

    # Данные из связанного профиля (если есть)
    # Используем Resolve методы Ninja для извлечения данных из связанной OneToOne модели
    phone: str | None = Field(default=None, description="Рабочий телефон (из профиля)")

    @staticmethod
    def resolve_phone(obj: User) -> str | None:
        """Извлекает телефон из связанного профиля, если он существует."""

        if hasattr(obj, "profile") and obj.profile:
            return obj.profile.phone

        return None
