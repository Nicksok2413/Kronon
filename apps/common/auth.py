"""
Custom authentification class and utils for Ninja API.
"""

from typing import cast

from django.conf import settings
from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import APIKeyHeader

from apps.common.types import NinjaRequest
from apps.users.constants import SYSTEM_USER_ID
from apps.users.models import User


class AsyncApiKeyAuth(APIKeyHeader):
    """
    Асинхронная аутентификация по API-ключу через заголовок 'X-API-Key'.
    Используется для межсервисного взаимодействия.
    """

    param_name = "X-API-Key"

    async def authenticate(self, request: HttpRequest, key: str | None) -> str | None:
        """
        Проверяет переданный ключ.
        Если ключ верен, возвращает строку (маркер для системы), что запрос пришел от системы, иначе None.

        Args:
            request (HttpRequest): Объект входящего запроса.
            key (str): Переданный API-ключ.

        Returns:
            str | None: Маркер для системы или None
        """
        if key == settings.INTERNAL_API_KEY:
            return "system_api"  # Маркер для системы, что это программный доступ

        return None


async def get_auth_identity(request: HttpRequest) -> User:
    """
    Извлекает объект User (реальный или системный) из запроса.

    Args:
        request (HttpRequest): Объект входящего запроса.

    Returns:
          User: объект пользователя, инициировавшего запрос.

    Raises:
        401: Не авторизован.
    """
    # Приводим тип запроса к интерфейсу NinjaRequest
    ninja_request = cast(NinjaRequest, request)

    # Ninja уже заполнил auth в аутентификаторе
    identity = ninja_request.auth

    # Если аутентификация по API-ключу (auth будет строкой "system_api")
    if identity == "system_api":
        # Возвращаем системного юзера из БД (Django кэширует get)
        system_user: User = await User.objects.aget(id=SYSTEM_USER_ID)
        return system_user

    # Если аутентификация по JWT (Ninja-JWT кладет объект User в auth),
    # проверяем, что в auth действительно User (а не None/Anonymous)
    if isinstance(identity, User):
        # Возвращаем объект пользователя
        return identity

    # Иначе - пробрасываем исключение
    raise HttpError(status_code=401, message="Не авторизован.")
