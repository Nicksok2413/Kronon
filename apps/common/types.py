"""
Common custom types of Kronon project.
"""

from typing import Annotated

from django.http import HttpRequest
from pydantic import AfterValidator

from apps.common.validators import validate_phone_pydantic
from apps.users.models import User

# Определяем возможные типы аутентификации
AuthType = str | User


class NinjaRequest(HttpRequest):
    """
    Типизированный запрос для Django Ninja.
    Объединяет стандартный HttpRequest и динамический атрибут auth (для типизации mypy).
    """

    auth: AuthType


# AfterValidator прогонит значение через функцию валидации телефона после базовой проверки строки
PhoneNumber = Annotated[
    str,
    AfterValidator(validate_phone_pydantic),  # Проверяет формат телефона через phonenumbers
]
