"""
Custom middleware for collecting pghistory context and security checks.
Fully Asynchronous implementation.
"""

import uuid
from typing import Any, cast

from django.conf import settings
from django.contrib.auth import alogout
from django.contrib.auth.models import AnonymousUser
from django.core.handlers.asgi import ASGIRequest as DjangoASGIRequest
from django.core.handlers.wsgi import WSGIRequest as DjangoWSGIRequest
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from jwt import PyJWTError, decode
from loguru import logger
from pghistory import config as pghistory_config
from pghistory import context as pghistory_context
from pghistory.middleware import ASGIRequest, WSGIRequest
from sentry_sdk import set_tag, set_user

from apps.users.constants import SYSTEM_USER_EMAIL, SYSTEM_USER_ID
from apps.users.models import User


class KrononHistoryMiddleware:
    """
    Полностью асинхронная единая точка входа для аудита, трассировки и безопасности.
    Адаптирована под логику оригинального HistoryMiddleware (подмена классов запроса).

    Добавляет ID корреляции, ID пользователя, Email пользователя, IP адрес, User-Agent,
    URL, HTTP-метод и сервис (источник запроса) в контекст pghistory с использованием ContextVars.

    Полезно сохранять Email пользователя, чтобы он остался в истории при удалении пользователя.
    """

    def __init__(self, get_response: Any):
        self.get_response = get_response

        # Флаги для Django, что middleware поддерживает async
        self.async_capable = True
        self.sync_capable = False

    async def __call__(self, request: HttpRequest) -> HttpResponseBase:
        """
        Асинхронная обработка запроса.

        Args:
            request (HttpRequest): Объект входящего HTTP запроса.

        Returns:
            HttpResponseBase: Объект HTTP ответа.
        """
        # Извлекаем или генерируем Correlation ID до начала обработки запроса
        correlation_id = request.headers.get("X-Correlation-ID") or request.META.get("HTTP_X_CORRELATION_ID")

        if not correlation_id:
            correlation_id = str(uuid.uuid7())

        # Сохраняем в объект запроса
        request.correlation_id = correlation_id  # type: ignore[attr-defined]

        # --- Безопасность: Force Logout ---

        # Вызываем нативный асинхронный метод
        user = await request.auser()

        # Проверка на Soft Delete (если админ удалил юзера - мгновенное разлогинивание)
        if user.is_authenticated and getattr(user, "is_deleted", False):
            logger.warning(f"Force logout for deleted user: {user}")

            # Нативный асинхронный логаут
            await alogout(request)

            # Возвращаем простой HTTP ответ вместо ошибки
            return HttpResponse("Account deactivated", status=401)

        # --- Sentry Tags (данные приклеятся ко всем ошибкам, возникшим в рамках запроса) ---

        set_tag("correlation_id", correlation_id)

        # --- Сбор контекста для pghistory ---

        audit_context = await self.get_audit_context(
            request=request,
            request_user=user,
            correlation_id=correlation_id,
        )

        service = audit_context.get("service")
        auth_type = "api_key" if service == "System" else "jwt/session"

        set_tag("service", service)
        set_tag("auth_type", auth_type)

        # Устанавливаем Sentry юзера на основе собранного контекста
        set_user({"id": str(audit_context.get("user")), "email": audit_context.get("user_email")})

        # --- Выполнение запроса с установкой ContextVars ---

        # logger.contextualize и pghistory.context работают через ContextVars,
        # что абсолютно безопасно и нативно поддерживается в asyncio

        # logger.contextualize привязывает extra данные к текущему контексту выполнения
        # correlation_id передаем в контекст для всех HTTP-методов
        with logger.contextualize(correlation_id=correlation_id):
            # Контекст pghistory только для разрешенных методов (PGHISTORY_MIDDLEWARE_METHODS)
            if request.method in pghistory_config.middleware_methods():
                with pghistory_context(**audit_context):
                    # Хак из pghistory: подменяем класс запроса, чтобы отслеживать позднее изменение request.user
                    if isinstance(request, DjangoWSGIRequest):
                        request.__class__ = WSGIRequest
                    elif isinstance(request, DjangoASGIRequest):
                        request.__class__ = ASGIRequest

                    # Вызываем следующий слой middleware / роутер (асинхронно)
                    response = cast(HttpResponseBase, await self.get_response(request))  # Явная типизация для mypy

            else:
                # Для неразрешенных методов вроде OPTIONS - идем дальше без pghistory.context
                response = cast(HttpResponseBase, await self.get_response(request))  # Явная типизация для mypy

            # Если это HttpResponseBase, добавляем заголовок (отдаем Correlation ID в ответ)
            if isinstance(response, HttpResponseBase):
                response["X-Correlation-ID"] = correlation_id  # Полезно для фронтенда/отладки

            return response

    async def get_audit_context(
        self, request: HttpRequest, request_user: User | AnonymousUser, correlation_id: str
    ) -> dict[str, Any]:
        """
        Асинхронно формирует словарь контекста для pghistory.

        Args:
            request (HttpRequest): Объект входящего HTTP запроса.
            request_user (User | AnonymousUser): Текущий пользователь, определенный Django (SessionAuth).
            correlation_id (str): ID корреляции (уникальная метка запроса для аналитика логов/ошибок).

        Returns:
            dict[str, Any]: Словарь с контекстом.
        """

        # Базовый контекст
        base_context: dict[str, Any] = {
            "url": request.path,
            "method": request.method,
            "correlation_id": correlation_id,
            "ip_address": self._get_ip_address(request),
            "user_agent": self._get_user_agent(request),
        }

        # Проверяем заголовки на наличие системного API-ключа
        api_key = request.headers.get("X-API-KEY") or request.META.get("HTTP_X_API_KEY")

        # Если нашли системный API-ключ
        if api_key == settings.INTERNAL_API_KEY:
            # Добавляем ID и Email системного юзера в базовый контекст
            base_context["user"] = str(SYSTEM_USER_ID)
            base_context["user_email"] = SYSTEM_USER_EMAIL
            base_context["service"] = "System"  # Помечаем сервис как System

            # Возвращаем словарь с контекстом
            return base_context

        # Иначе - это API/Web
        base_context["service"] = "API/Web"
        user_id = None
        user_email = None

        # Проверяем JWT Auth (Swagger / Frontend)
        auth_header = request.headers.get("Authorization", "")

        # Даем ему приоритет над сессией, чтобы Swagger честно логировал от имени токена,
        # даже если в браузере висит кука авторизованного админа
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

            try:
                # Декодируем токен без проверки подписи (это мгновенно)
                # Валидацию подписи всё равно сделает Ninja позже
                payload = decode(token, options={"verify_signature": False}, algorithms=["HS256"])

                # Явно приводим динамический ключ из настроек к строке для mypy
                claim_key = cast(str, settings.NINJA_JWT.get("USER_ID_CLAIM", "user_id"))

                token_user_id = payload.get(claim_key)

                if token_user_id:
                    user_id = str(token_user_id)
                    # Используем асинхронный .afirst для email
                    user_email = await User.objects.filter(id=token_user_id).values_list("email", flat=True).afirst()

            except PyJWTError as exc:
                # Токен недействителен, просрочен или поврежден
                # Логируем ошибку, Ninja JWT отловит это позже и вернет 401
                logger.debug(f"JWT parsing failed in middleware: {exc}")

        # Проверяем Session Auth (Админка Django) - если нет валидного JWT
        if not user_id and request_user.is_authenticated:
            user_id = str(request_user.id)
            user_email = getattr(request_user, "email", None)

        # Добавляем ID и Email юзера в базовый контекст
        base_context["user"] = user_id
        base_context["user_email"] = user_email

        # Возвращаем словарь с контекстом
        return base_context

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
            request (HttpRequest): Объект входящего HTTP запроса.

        Returns:
            str: User-Agent или "Unknown".
        """
        user_agent = request.META.get("HTTP_USER_AGENT", "Unknown")[:255]  # Ограничиваем длину для БД
        return cast(str, user_agent)  # Явная типизация для mypy
