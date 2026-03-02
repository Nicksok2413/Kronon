"""
Custom authentification class for Ninja API.
"""

from django.conf import settings
from django.http import HttpRequest
from ninja.security import APIKeyHeader


class AsyncApiKeyAuth(APIKeyHeader):
    """
    Асинхронная аутентификация по API-ключу через заголовок 'X-API-Key'.
    Используется для межсервисного взаимодействия или вебхуков.
    """

    param_name = "X-API-Key"

    async def authenticate(self, request: HttpRequest, key: str) -> str | None:
        """
        Проверяет переданный ключ.
        Возвращает строку (помечает пользователя), если ключ верен, иначе None.

        Args:
            request (HttpRequest): Объект входящего запроса.
            key (str): Переданный API-ключ.

        Returns:
            str | None: Метка пользователя или None.
        """
        if settings.INTERNAL_API_KEY and key == settings.INTERNAL_API_KEY:
            return "api_key_user"  # Условный маркер, что запрос пришел от системы

        return None
