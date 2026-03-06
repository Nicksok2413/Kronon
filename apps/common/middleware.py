"""
Custom middleware for collecting pghistory context.
"""

from typing import Any, cast

from django.http import HttpRequest
from pghistory.middleware import HistoryMiddleware

from apps.users.constants import SYSTEM_USER_ID


class KrononHistoryMiddleware(HistoryMiddleware):
    """
    Расширенный middleware для фиксации контекста pghistory с поддержкой System API.
    Добавляет IP адрес, метод, источник и email пользователя в контекст.
    """

    @staticmethod
    def _get_ip_address(request: HttpRequest) -> str | None:
        """
        Вспомогательный метод для получения IP адреса с учетом прокси.

        Args:
            request (HttpRequest): Объект входящего запроса.

        Returns:
            str: Строка с IP адресом.
        """
        x_forwarded = request.META.get("HTTP_X_FORWARDED_FOR")

        if x_forwarded and isinstance(x_forwarded, str):
            # Берем первый IP из списка (адрес клиента до прокси)
            ip_address = x_forwarded.split(",")[0].strip()

            return cast(str, ip_address)  # Явная типизация для mypy

        remote_addr = request.META.get("REMOTE_ADDR")

        if remote_addr and isinstance(remote_addr, str):
            return cast(str, remote_addr)  # Явная типизация для mypy

        return None

    @staticmethod
    def _get_user_email(request: HttpRequest) -> str | None:
        """
        Вспомогательный метод для получения Email пользователя.
        Полезно сохранить email, чтобы он остался в истории при удалении юзера.

        Args:
            request (HttpRequest): Объект входящего запроса.

        Returns:
            str | None: Email пользователя или None.
        """
        if request.user.is_authenticated:
            return getattr(request.user, "email", None)

        return None

    @staticmethod
    def _get_user_agent(request: HttpRequest) -> str:
        """
        Вспомогательный метод для получения User-Agent.

        Args:
            request (HttpRequest): Объект входящего запроса.

        Returns:
            str: User-Agent или "Unknown".
        """
        return request.META.get("HTTP_USER_AGENT", "Unknown")[:255]  # Ограничиваем длину для БД

    def get_context(self, request: HttpRequest) -> dict[str, Any]:
        """
        Формирует словарь контекста.
        Базовый метод добавляет 'user' (ID) и 'url' (эндпойнт).

        Добавляем:
            'app_source': источник изменения (API/Web),
            'method': HTTP метод,
            'ip_address': IP адрес,
            'user_agent': User-Agent,
            'user_email': Email пользователя.

        Args:
            request (HttpRequest): Объект входящего запроса.

        Returns:
            dict[str, Any]: Обновленный словарь контекста.
        """
        # Базовый контекст (user и url)
        base_context = super().get_context(request)

        # Переопределяем 'user', если Ninja опознал системный API-ключ
        if getattr(request, "auth", None) == "system_api":
            base_context["user"] = SYSTEM_USER_ID

        # Получаем IP адрес (с учетом прокси)
        ip_address = self._get_ip_address(request)

        # Получаем User-Agent
        user_agent = self._get_user_agent(request)

        # Получаем Email пользователя
        user_email = self._get_user_email(request)

        # Обновляем словарь контекста
        return base_context | {
            "app_source": "API/Web",
            "method": request.method,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "user_email": user_email,
        }
