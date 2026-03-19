"""
Custom middleware for collecting pghistory context.
"""

import uuid
from typing import Any, cast

from asgiref.sync import async_to_sync
from django.conf import settings
from django.contrib.auth import alogout
from django.http import HttpRequest, HttpResponse
from loguru import logger
from pghistory.middleware import HistoryMiddleware
from sentry_sdk import set_tag, set_user

from apps.users.constants import SYSTEM_USER_EMAIL, SYSTEM_USER_ID


class KrononHistoryMiddleware(HistoryMiddleware):
    """
    Единая точка входа для аудита, трассировки ID корреляции и безопасности.
    Адаптирована под асинхронный logout и системный API-инструментарий.
    Использует async_to_sync, чтобы безопасно вызвать асинхронные методы в синхронном middleware.
    Добавляет ID корреляции, Email пользователя, IP адрес, User-Agent, HTTP-метод и сервис в контекст pghistory.
    """

    def __call__(self, request: HttpRequest) -> HttpResponse:
        """
        Асинхронная обработка запроса.
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

        # --- Безопасность: Force Logout ---

        # Используем auser(), чтобы не вызывать синхронный доступ к БД
        user = async_to_sync(request.auser)()

        # Проверка на Soft Delete (если админ удалил юзера - мгновенное разлогинивание)
        if user.is_authenticated and getattr(user, "is_deleted", False):
            logger.warning(f"Force logout for deleted user: {user}")

            # Используем alogout(), чтобы не вызывать синхронный доступ к БД
            async_to_sync(alogout)(request)  # Force Logout

            return HttpResponse("Account deactivated", status=401)

        # --- Sentry (данные приклеятся ко всем ошибкам, возникшим в рамках запроса) ---

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
            set_user({"id": str(user.id), "email": self._get_user_email(request)})
            set_tag("auth_type", "jwt/session")
            set_tag("service", "API/Web")

        # --- Аудит: pghistory + Loguru ---

        # logger.contextualize привязывает extra данные к текущему контексту выполнения
        with logger.contextualize(correlation_id=correlation_id):
            # Вызываем родительский __call__ (он внутри себя вызовет get_context)
            response: HttpResponse = super().__call__(request)  # type: ignore[no-untyped-call]

            # Если это HttpResponse, добавляем заголовок (отдаем Correlation ID обратно в Response)
            if isinstance(response, HttpResponse):
                response["X-Correlation-ID"] = correlation_id  # Полезно для фронтенда/отладки

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
        user = request.user

        if user and user.is_authenticated:
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
        Формирует расширенный словарь контекста (вызывается внутри super().__call__).

        Добавляет в контекст кроме базовых 'user' (ID) и 'url' (эндпойнт):
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
