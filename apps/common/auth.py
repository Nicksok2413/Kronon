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


async def get_request_initiator(request: HttpRequest) -> tuple[UUID, str]:
    """
    Возвращает данные инициатора запроса к API (UUID для pghistory, строка для логов).
    Строка для логов собирается с учетом настроек приватности.

    Args:
        request (HttpRequest): Объект входящего запроса.

    Returns:
        tuple[UUID, str]: (UUID инициатора запроса, строка для логирования).
    """
    log_details = ""

    # Добавляем детали (IP адрес и User-Agent), если включен флаг в .env
    if settings.LOG_DETAILED_AUDIT:
        # IP адрес (с учетом прокси)
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
        # Берем первый IP из списка (адрес клиента до прокси) или REMOTE_ADDR
        ip_address = x_forwarded.split(",")[0].strip() if x_forwarded else request.META.get("REMOTE_ADDR", "no-ip")

        # User-Agent
        user_agent = request.META.get("HTTP_USER_AGENT", "no-ua")

        log_details = f" [IP: {ip_address}, User-Agent: {user_agent}]"

    try:
        # Получаем пользователя из запроса
        user = await get_auth_identity(request)

        # Собираем строку для логов
        log_message = f"{user.email}" + log_details

        # Возвращаем UUID пользователя и информацию для логов
        return user.id, log_message

    except HttpError:
        # Если аутентификация не пройдена (например, в публичном эндпоинте)
        return SYSTEM_USER_ID, "Anonymous" + log_details
