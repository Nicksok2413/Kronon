"""
Custom authentification class and utils for Ninja API.
"""

from typing import cast
from uuid import UUID

from django.conf import settings
from django.http import HttpRequest
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


async def get_initiator_id(request: HttpRequest) -> UUID | None:
    """
    Извлекает ID пользователя из HTTP-запроса для передачи в слой сервисов (для аудита).

    Безопасно обрабатывает асинхронные запросы (auser) и системные запросы по API-ключу.

    Args:
        request (HttpRequest): Объект входящего запроса.

    Returns:
        UUID: ID пользователя, инициировавшего запрос.
        None: Если это программный запрос (от system_api).
    """
    # Приводим тип запроса к интерфейсу NinjaRequest
    ninja_request = cast(NinjaRequest, request)

    # Если это программный запрос по API-ключу, пользователя в БД нет
    if ninja_request.auth == "system_api":
        return None

    # Безопасное асинхронное получение пользователя (распаковывает SimpleLazyObject)
    # Эндпоинты защищены, поэтому в запросе User (анонимных юзеров не может быть)
    # Но .auser возвращает AbstractBaseUser | AnonymousUser, поэтому используем cast для mypy
    user = cast(User, await request.auser())

    return getattr(user, "id", None)
