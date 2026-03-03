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


async def get_request_initiator(request: HttpRequest) -> tuple[UUID | None, str]:
    """
    Извлекает из запроса ID пользователя (для аудита pghistory в слое сервисов).
    Возвращает пару (UUID для БД, Строка для логов).

    Args:
        request (HttpRequest): Объект входящего запроса.

    Returns:
        tuple[UUID | None, str]:
            - UUID пользователя или None (для системных запросов или в публичном эндпойнте).
            - Строковое представление для логирования (ID, "System_API" или "Anonymous").
    """
    try:
        # Идентифицируем личность в запросе
        auth_identity = await get_auth_identity(request)

        # Если это система (ID пользователя в БД отсутствует), возвращаем tuple[None, "System_API"]
        if auth_identity == "system_api":
            return None, "System_API"

        # user = cast(User, identity)  # Явная типизация для Mypy: identity — это User

        # Если в auth_identity лежит объект пользователя, возвращаем его tuple[UUID, str(UUID)]
        if isinstance(auth_identity, User):
            user_id = auth_identity.id
            return user_id, str(user_id)

    except HttpError:
        # Если аутентификация не пройдена (например, в публичном эндпоинте)
        return None, "Anonymous"
