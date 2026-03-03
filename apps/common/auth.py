"""
Custom authentification class and utils for Ninja API.
"""

from typing import cast
from uuid import UUID

from django.conf import settings
from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import APIKeyHeader

from apps.common.types import NinjaRequest
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
        if settings.INTERNAL_API_KEY and key == settings.INTERNAL_API_KEY:
            return "system_api"  # Маркер для системы, что это программный доступ

        return None


async def get_auth_identity(request: HttpRequest) -> User | str:
    """
    Извлекает личность (объект User или системный маркер "system_api") из запроса.

    Args:
        request (HttpRequest): Объект входящего запроса.

    Returns:
          User: объект авторизованного пользователя, инициировавшего запрос.
          str: Маркер ("system_api"), что запрос пришел от системы
    """
    # Приводим тип запроса к интерфейсу NinjaRequest
    ninja_request = cast(NinjaRequest, request)

    # Ninja уже заполнил auth в аутентификаторе
    identity = ninja_request.auth

    # Если аутентификация по API-ключу (auth будет строкой "system_api")
    if identity == "system_api":
        # Возвращаем строку с системным маркером
        return "system_api"

    # Если аутентификация по JWT (Ninja-JWT кладет объект User в auth),
    # проверяем, что в auth действительно User (а не None/Anonymous)
    if isinstance(identity, User):
        # Возвращаем объект пользователя
        return identity

    # Иначе - пробрасываем исключение
    raise HttpError(status_code=401, message="Не авторизован.")


async def get_initiator_id(request: HttpRequest) -> UUID | None:
    """
    Извлекает ID пользователя из запроса для передачи в слой сервисов (для аудита).

    Args:
        request (HttpRequest): Объект входящего запроса.

    Returns:
        UUID: ID пользователя, инициировавшего запрос.
        None: Если это программный запрос (от system_api).
    """
    try:
        # Идентифицируем личность в запросе
        auth_identity = await get_auth_identity(request)

        # Если в auth_identity лежит объект пользователя, возвращаем его ID
        # Если это система ("system_api"), ID пользователя в БД отсутствует, возвращаем None
        return auth_identity.id if isinstance(auth_identity, User) else None

    except HttpError:
        # Если аутентификация не пройдена (например, в публичном эндпоинте)
        return None
