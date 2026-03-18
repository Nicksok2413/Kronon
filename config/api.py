"""
Root API Configuration.
"""

# from typing import Callable

# from django.http import HttpRequest, HttpResponse
from ninja_extra import NinjaExtraAPI
from ninja_jwt.authentication import AsyncJWTAuth
from ninja_jwt.controller import NinjaJWTDefaultController

# from pghistory import context as pghistory_context
from apps.audit.api.v1 import router as audit_router
from apps.clients.api.v1 import router as clients_router
from apps.common.auth import AsyncApiKeyAuth
from apps.common.exceptions import setup_exception_handlers

# from apps.users.constants import SYSTEM_USER_ID


# def ninja_audit_user_patch(request: HttpRequest, get_response: Callable) -> HttpResponse:
#     """
#     Патч-middleware для NinjaExtraAPI для синхронизации контекста аудита.
#
#     Захватывает данные аутентификации (JWT/API-Key) и дополняет контекст пользователем (user).
#
#     Args:
#         request: Объект входящего HTTP запроса.
#         get_response: Функция для продолжения цепочки обработки.
#
#     Returns:
#         Объект ответа с установленным пользователем (user).
#     """
#
#     # Выполняем запрос (здесь Ninja проверит Auth и заполнит request.user)
#     response = get_response(request)
#
#     user = request.user.id if request.user.is_authenticated else None
#
#     # Определяем инициатора запроса (User или System API)
#     if getattr(request, "auth", None) == "system_api":
#         user = SYSTEM_USER_ID
#
#     # Дополняем контекст pghistory (объединяется с контекстом из Django Middleware)
#     # pghistory.context умеет обновлять существующий контекст в рамках одного потока
#     with pghistory_context(user=user):
#         return response
#
# api.add_middleware(ninja_audit_user_patch)


# Инициализируем API
# NinjaExtraAPI дает больше возможностей, чем просто NinjaAPI
api = NinjaExtraAPI(
    title="Kronon API",
    version="1.0.0",
    description="Enterprise Accounting OS API",
    urls_namespace="api",  # Важно для reverse()
    auth=[AsyncJWTAuth(), AsyncApiKeyAuth()],  # Аутентификация по умолчанию для всех эндпоинтов
)


# --- Подключение контроллеров ---

# Авторизация (получение токена, рефреш)
# Эндпоинты: /api/token/pair, /api/token/refresh, /api/token/verify
api.register_controllers(NinjaJWTDefaultController)


# --- Подключаем роутеры приложений ---

# Аудит
api.add_router("/audit", audit_router, tags=["Audit"])

# Клиенты
api.add_router("/clients", clients_router, tags=["Clients"])


# --- Подключаем обработчики ошибок ---
setup_exception_handlers(api)
