"""
Custom middleware for collecting pghistory context and security checks.
Hybrid Asynchronous/Synchronous implementation based on Django 6.0 docs.
"""

import uuid
from typing import Any, cast

from asgiref.sync import iscoroutinefunction
from django.conf import settings
from django.contrib.auth import alogout, logout
from django.contrib.auth.models import AnonymousUser
from django.core.handlers.asgi import ASGIRequest as DjangoASGIRequest
from django.core.handlers.wsgi import WSGIRequest as DjangoWSGIRequest
from django.http import HttpRequest, HttpResponse
from django.http.response import HttpResponseBase
from django.utils.decorators import sync_and_async_middleware
from jwt import PyJWTError, decode
from loguru import logger
from pghistory.middleware import ASGIRequest, WSGIRequest
from sentry_sdk import set_tag, set_user

from apps.audit.utils import get_ip_address, get_user_agent
from apps.users.constants import SYSTEM_USER_EMAIL, SYSTEM_USER_ID
from apps.users.models import User

# ==============================================================================
# DRY HELPERS (общие вспомогательные функции)
# ==============================================================================


def _get_correlation_id(request: HttpRequest) -> str:
    """
    Извлекает или генерирует ID корреляции (уникальная метка запроса для аналитика логов/ошибок).

    Args:
        request (HttpRequest): Объект HTTP запроса.

    Returns:
        str: ID корреляции.
    """
    correlation_id = request.headers.get("X-Correlation-ID") or request.META.get("HTTP_X_CORRELATION_ID")

    if not correlation_id:
        correlation_id = str(uuid.uuid7())

    # Сохраняем в объект запроса
    request.correlation_id = correlation_id  # type: ignore[attr-defined]

    return correlation_id


def _apply_sentry(audit_context: dict[str, Any], correlation_id: str) -> None:
    """
    Устанавливает теги и юзера в Sentry на основе собранного контекста.

    Args:
        audit_context (dict[str, Any]): Словарь с контекстом
        correlation_id (str): ID корреляции.
    """
    set_tag("correlation_id", correlation_id)
    set_user({"id": str(audit_context.get("user")), "email": audit_context.get("user_email")})

    service = audit_context.get("service")
    auth_type = "api_key" if service == "System" else "jwt/session"

    set_tag("service", service)
    set_tag("auth_type", auth_type)


def _patch_request_class(request: HttpRequest) -> None:
    """
    Хак pghistory: подменяем класс запроса для отслеживания поздней авторизации.

    Args:
        request (HttpRequest): Объект HTTP запроса.
    """
    if isinstance(request, DjangoWSGIRequest):
        request.__class__ = WSGIRequest
    elif isinstance(request, DjangoASGIRequest):
        request.__class__ = ASGIRequest


def _process_response(response: HttpResponseBase, correlation_id: str) -> HttpResponseBase:
    """
    Добавляет заголовок 'X-Correlation-ID' с ID корреляции к ответу.

    Args:
        response (HttpResponseBase): Объект HTTP ответа.
        correlation_id (str): ID корреляции.

    Returns:
        HttpResponseBase: HTTP ответ с ID корреляции.
    """
    if hasattr(response, "__setitem__"):
        # Полезно для фронта/отладки
        response["X-Correlation-ID"] = correlation_id

    return response


# ==============================================================================
# AUDIT CONTEXT BUILDERS (сборка контекста)
# ==============================================================================


def _prepare_audit_context(request: HttpRequest, correlation_id: str) -> dict[str, Any]:
    """
    Формирует базовый словарь контекста для pghistory.

    Проверяет наличие системного API-ключа в заголовках.
    Если в запросе системны API-ключ - добавляет ID и Email системного юзера в контекст.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        correlation_id (str): ID корреляции.

    Returns:
        dict[str, Any]: Словарь контекста.
    """
    # Базовый словарь контекста
    base_context: dict[str, Any] = {
        "url": request.path,  # URL
        "method": request.method,  # HTTP-метод
        "correlation_id": correlation_id,  # ID корреляции
        "ip_address": get_ip_address(request),  # IP адрес
        "user_agent": get_user_agent(request),  # User-Agent
    }

    # Проверяем заголовки на наличие системного API-ключа
    api_key = request.headers.get("X-API-KEY") or request.META.get("HTTP_X_API_KEY")

    # Если нашли системный API-ключ
    if api_key == settings.INTERNAL_API_KEY:
        # Добавляем ID и Email системного юзера в словарь контекста
        base_context["user"] = str(SYSTEM_USER_ID)
        base_context["user_email"] = SYSTEM_USER_EMAIL
        base_context["service"] = "System"  # Помечаем сервис как System

    # Иначе - это API/Web
    else:
        base_context["service"] = "API/Web"  # Помечаем сервис как API/Web

    # Возвращаем словарь контекста
    return base_context


def _parse_jwt_user_id(request: HttpRequest) -> str | None:
    """
    Парсит токен и возвращает ID пользователя, если токен валиден.

    Args:
        request (HttpRequest): Объект HTTP запроса.

    Returns:
        str | None: ID пользователя или None.
    """
    # Проверяем JWT Auth (Swagger / Frontend)
    auth_header = request.headers.get("Authorization", "")

    # Даем ему приоритет над сессией, чтобы Swagger честно логировал от имени токена,
    # даже если в браузере висит кука авторизованного админа
    if auth_header.startswith("Bearer "):
        token = auth_header.split(" ")[1]

        try:
            # Декодируем токен без проверки подписи (это мгновенно)
            # Валидацию подписи всё равно сделает Ninja позже
            payload = decode(token, algorithms=["HS256"], options={"verify_signature": False})

            # Явно приводим динамический ключ из настроек к строке для mypy
            claim_key = cast(str, settings.NINJA_JWT.get("USER_ID_CLAIM", "user_id"))

            # Получаем ID пользователя
            token_user_id = payload.get(claim_key)

            return str(token_user_id) if token_user_id else None

        except PyJWTError as exc:
            # Токен недействителен, просрочен или поврежден
            # Логируем ошибку, Ninja JWT отловит это позже и вернет 401
            logger.debug(f"JWT parsing failed in middleware: {exc}")
            pass

    return None


def _finalize_audit_context(
    base_context: dict[str, Any], user_id: str | None, user_email: str | None, request_user: User | AnonymousUser
) -> dict[str, Any]:
    """
    Добавляет данные Session Auth (если JWT нет) и финализирует словарь контекста.

    Args:
        base_context (dict[str, Any]): Базовый словарь контекста.
        user_id (str | None): ID пользователя или None.
        user_email (str | None): Email пользователя или None.
        request_user (User | AnonymousUser): Текущий пользователь, определенный Django (Session Auth).

    Returns:
        dict[str, Any]: Финальный словарь контекста.
    """

    # Проверяем Session Auth (Админка Django) - если нет валидного JWT
    if not user_id and request_user.is_authenticated:
        user_id = str(request_user.id)
        user_email = getattr(request_user, "email", None)

    # Добавляем ID и Email юзера в словарь контекста
    base_context.update({"user": user_id, "user_email": user_email})

    # Возвращаем финальный словарь контекста
    return base_context


async def _get_audit_context_async(
    request: HttpRequest, request_user: User | AnonymousUser, correlation_id: str
) -> dict[str, Any]:
    """
    Асинхронная сборка контекста pghistory (для Ninja/Uvicorn).

    Args:
        request (HttpRequest): Объект HTTP запроса.
        request_user (User | AnonymousUser): Текущий пользователь, определенный Django (SessionAuth).
        correlation_id (str): ID корреляции.

    Returns:
        dict[str, Any]: Словарь с контекстом.
    """

    # Базовый контекст
    base_context = _prepare_audit_context(request=request, correlation_id=correlation_id)

    # Если сервис помечен как системный
    if base_context["service"] == "System":
        # Возвращаем базовый контекст
        return base_context

    # Иначе - это API/Web

    # Парсим JWT-токен и получаем ID юзера, если токен валидный
    user_id = _parse_jwt_user_id(request)
    user_email = None

    # Если получили ID юзера из JWT Auth, достаем email из БД
    if user_id:
        # Используем асинхронный .afirst()
        user_email = await User.objects.filter(id=user_id).values_list("email", flat=True).afirst()

    # Финализируем и возвращаем словарь контекста
    return _finalize_audit_context(
        base_context=base_context,
        user_id=user_id,
        user_email=user_email,
        request_user=request_user,
    )


def _get_audit_context_sync(
    request: HttpRequest, request_user: User | AnonymousUser, correlation_id: str
) -> dict[str, Any]:
    """
    Синхронная сборка контекста pghistory (для Admin Panel).

    Args:
        request (HttpRequest): Объект HTTP запроса.
        request_user (User | AnonymousUser): Текущий пользователь, определенный Django (SessionAuth).
        correlation_id (str): ID корреляции.

    Returns:
        dict[str, Any]: Словарь с контекстом.
    """

    # Базовый контекст
    base_context = _prepare_audit_context(request=request, correlation_id=correlation_id)

    # Если сервис помечен как системный
    if base_context["service"] == "System":
        # Возвращаем базовый контекст
        return base_context

    # Иначе - это API/Web

    # Парсим JWT-токен и получаем ID юзера, если токен валидный
    user_id = _parse_jwt_user_id(request)
    user_email = None

    # Если получили ID юзера из JWT Auth, достаем email из БД
    if user_id:
        # Используем синхронный .first()
        user_email = User.objects.filter(id=user_id).values_list("email", flat=True).first()

    # Финализируем и возвращаем словарь контекста
    return _finalize_audit_context(
        base_context=base_context,
        user_id=user_id,
        user_email=user_email,
        request_user=request_user,
    )


# ==============================================================================
# MAIN MIDDLEWARE (FACTORY FUNCTION)
# ==============================================================================


@sync_and_async_middleware
def kronon_history_middleware(get_response: Any) -> Any:
    """
    Фабрика гибридного middleware по стандартам Django 6.0.
    Определяет тип следующего слоя в цепочке при инициализации сервера.
    Использует @sync_and_async_middleware для гарантии сохранности ContextVars в гибридном ASGI/WSGI окружении.

    Добавляет ID корреляции, ID пользователя, Email пользователя, IP адрес, User-Agent,
    URL, HTTP-метод и сервис (источник запроса) в контекст pghistory с использованием ContextVars.
    Полезно сохранять Email пользователя, чтобы он остался в истории при удалении пользователя.

    Адаптирована под логику оригинального HistoryMiddleware (подмена классов запроса).
    """

    # Проверяем, является ли следующий обработчик асинхронным
    is_async = iscoroutinefunction(get_response)

    if is_async:

        async def async_middleware(request: HttpRequest) -> HttpResponseBase:
            """
            Асинхронная ветка (выполняется в Event Loop для Uvicorn / Ninja API).

            Args:
                request (HttpRequest): Объект HTTP запроса.

            Returns:
                HttpResponseBase: Объект HTTP ответа.
            """
            # Извлекаем или генерируем Correlation ID до начала обработки запроса
            correlation_id = _get_correlation_id(request)

            # --- Безопасность: Force Logout ---

            # Вызываем асинхронный .auser()
            user = await request.auser()

            # Проверка на Soft Delete (если админ удалил юзера - мгновенное разлогинивание)
            if user.is_authenticated and getattr(user, "is_deleted", False):
                logger.warning(f"Force logout for deleted user: {user}")
                # Вызываем асинхронный .alogout()
                await alogout(request)
                # Возвращаем простой HTTP ответ вместо ошибки
                return HttpResponse("Account deactivated", status=401)

            # --- Собираем и прикрепляем контекст ---

            audit_context = await _get_audit_context_async(
                request=request,
                request_user=user,
                correlation_id=correlation_id,
            )

            # Сохраняем контекст в объект запроса
            request.audit_context = audit_context  # type: ignore[attr-defined]

            # Устанавливает теги Sentry (данные приклеятся ко всем ошибкам, возникшим в рамках запроса)
            _apply_sentry(audit_context=audit_context, correlation_id=correlation_id)

            # logger.contextualize привязывает extra данные к текущему контексту выполнения
            # correlation_id передаем в контекст для всех HTTP-методов
            with logger.contextualize(correlation_id=correlation_id):
                # Патчим класс запроса (хак из pghistory)
                _patch_request_class(request)
                # Асинхронно вызываем следующий слой middleware / роутер
                response = cast(HttpResponseBase, await get_response(request))  # Явная типизация для mypy
                # Добавляем заголовок 'X-Correlation-ID' (отдаем Correlation ID в ответ)
                return _process_response(response=response, correlation_id=correlation_id)

        return async_middleware

    else:

        def sync_middleware(request: HttpRequest) -> HttpResponseBase:
            """
            Синхронная ветка (выполняется в Thread Pool для Django Admin).

            Args:
                request (HttpRequest): Объект HTTP запроса.

            Returns:
                HttpResponseBase: Объект HTTP ответа.
            """
            # Извлекаем или генерируем Correlation ID до начала обработки запроса
            correlation_id = _get_correlation_id(request)

            # --- Безопасность: Force Logout ---

            user = request.user

            # Проверка на Soft Delete (если админ удалил юзера - мгновенное разлогинивание)
            if user.is_authenticated and getattr(user, "is_deleted", False):
                logger.warning(f"Force logout for deleted user: {user}")
                # Вызываем синхронный .logout()
                logout(request)
                # Возвращаем простой HTTP ответ вместо ошибки
                return HttpResponse("Account deactivated", status=401)

            # --- Собираем и прикрепляем контекст ---

            audit_context = _get_audit_context_sync(
                request=request,
                request_user=user,
                correlation_id=correlation_id,
            )

            # Сохраняем контекст в объект запроса
            request.audit_context = audit_context  # type: ignore[attr-defined]

            # Устанавливает теги Sentry (данные приклеятся ко всем ошибкам, возникшим в рамках запроса)
            _apply_sentry(audit_context=audit_context, correlation_id=correlation_id)

            # logger.contextualize привязывает extra данные к текущему контексту выполнения
            # correlation_id передаем в контекст для всех HTTP-методов
            with logger.contextualize(correlation_id=correlation_id):
                # Патчим класс запроса (хак из pghistory)
                _patch_request_class(request)
                # Синхронно вызываем следующий слой middleware / роутер
                response = cast(HttpResponseBase, get_response(request))  # Явная типизация для mypy
                # Добавляем заголовок 'X-Correlation-ID' (отдаем Correlation ID в ответ)
                return _process_response(response=response, correlation_id=correlation_id)

        return sync_middleware
