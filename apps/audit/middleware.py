"""
Custom middleware for collecting pghistory context.
"""

import uuid
from typing import Any, cast

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from loguru import logger
from pghistory.middleware import HistoryMiddleware
from sentry_sdk import set_tag, set_user

from apps.users.constants import SYSTEM_USER_EMAIL, SYSTEM_USER_ID


class KrononHistoryMiddleware(HistoryMiddleware):
    """
    Расширенный middleware для фиксации контекста pghistory с поддержкой System API.
    Добавляет Email пользователя, IP адрес, User-Agent, HTTP-метод и сервис (источник изменения объекта) в контекст.
    """

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Переопределяем метод вызова для проброса ID корреляции в Response.

        Args:
            request (HttpRequest): Объект входящего HTTP запроса.
        """
        # Извлекаем или генерируем Correlation ID до начала обработки запроса
        correlation_id = request.headers.get("X-Correlation-ID") or request.META.get("HTTP_X_CORRELATION_ID")

        if not correlation_id:
            correlation_id = str(uuid.uuid7())

        # Сохраняем в объект запроса
        request.correlation_id = correlation_id  # type: ignore[attr-defined]

        # Данные для Sentry: приклеятся ко всем ошибкам, возникшим в рамках этого запроса
        set_tag("correlation_id", correlation_id)

        # Проверяем заголовки на наличие системного API-ключа
        api_key = request.headers.get("X-API-KEY") or request.META.get("HTTP_X_API_KEY")

        # Если нашли системный API-ключ
        if api_key == settings.INTERNAL_API_KEY:
            set_user({"id": str(SYSTEM_USER_ID), "email": SYSTEM_USER_EMAIL})
            set_tag("auth_type", "api_key")
            set_tag("service", "System")

        # Иначе - это JWT-юзер
        else:
            user_id = getattr(request.user, "id", None)
            user_email = self._get_user_email(request)
            set_user({"id": str(user_id), "email": user_email})
            set_tag("auth_type", "jwt/session")
            set_tag("service", "API/Web")

        # logger.contextualize привязывает extra данные к текущему контексту выполнения
        with logger.contextualize(correlation_id=correlation_id):
            # Отдаем Correlation ID обратно в Response (полезно для фронтенда/отладки)
            response: HttpResponse = super().__call__(request)  # type: ignore[no-untyped-call]
            response["X-Correlation-ID"] = correlation_id
            return response

    @staticmethod
    def _get_user_email(request: HttpRequest) -> str | None:
        """
        Вспомогательный метод для получения Email пользователя.
        Полезно сохранить Email, чтобы он остался в истории при удалении юзера.

        Args:
            request (HttpRequest): Объект входящего HTTP запроса.

        Returns:
            str | None: Email пользователя или None.
        """
        user = getattr(request, "user", None)

        if user and getattr(user, "is_authenticated", False):
            return getattr(user, "email", None)

        return None

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
    def _get_user_agent(request: HttpRequest) -> str:
        """
        Вспомогательный метод для получения User-Agent.

        Args:
            request (HttpRequest): Объект входящего запроса.

        Returns:
            str: User-Agent или "Unknown".
        """
        user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")[:255]  # Ограничиваем длину для БД

        return cast(str, user_agent)  # Явная типизация для mypy

    def get_context(self, request: HttpRequest) -> dict[str, Any]:
        """
        Формирует расширенный словарь контекста.
        Базовый метод добавляет 'user' (ID) и 'url' (эндпойнт) в контекст.

        Добавляем:
            'correlation_id': ID корреляции (уникальная метка запроса для аналитика логов/ошибок),
            'user_email': Email пользователя,
            'ip_address': IP адрес,
            'user_agent': User-Agent,
            'method': HTTP метод,
            'service': Сервис - источник изменения объекта (API/Web).

        Args:
            request (HttpRequest): Объект входящего HTTP запроса.

        Returns:
            dict[str, Any]: Обновленный словарь контекста.
        """
        # Базовый контекст (user и url)
        base_context = super().get_context(request)

        # Проверяем заголовки на наличие системного API-ключа
        api_key = request.headers.get("X-API-KEY") or request.META.get("HTTP_X_API_KEY")

        # Если нашли системный API-ключ
        if api_key == settings.INTERNAL_API_KEY:
            # Переопределяем ID юзера на системного в базовом контексте
            base_context["user"] = SYSTEM_USER_ID
            # Добавляем Email системного юзера в базовый контекст
            base_context["user_email"] = SYSTEM_USER_EMAIL
            service = "System"

        # Иначе - это JWT-юзер
        else:
            # Добавляем Email JWT-юзера в базовый контекст
            base_context["user_email"] = self._get_user_email(request)
            service = "API/Web"

        # Получаем Correlation ID (уже созданный в __call__)
        correlation_id = getattr(request, "correlation_id", None)

        # Обновляем словарь контекста
        return base_context | {
            "correlation_id": correlation_id,
            "ip_address": self._get_ip_address(request),
            "user_agent": self._get_user_agent(request),
            "method": request.method,
            "service": service,
        }
