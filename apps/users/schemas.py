"""
Схемы данных (DTO) для Пользователей и Отделов.
"""

import uuid

from ninja import Schema

from apps.users.models import UserRole


class DepartmentOut(Schema):
    """
    Схема вывода информации об отделе (краткая).
    """

    id: uuid.UUID
    name: str


class UserOut(Schema):
    """
    Схема вывода информации о сотруднике (краткая).
    Используется для отображения ответственных лиц.
    """

    id: uuid.UUID
    email: str
    last_name: str
    first_name: str
    middle_name: str
    role: UserRole

    # Вычисляемое поле (Computed Field)
    # Ninja/Pydantic умеет вызывать методы модели, если имя совпадает
    full_name_rus: str
