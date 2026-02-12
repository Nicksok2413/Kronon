"""
Root API Configuration.
"""

from django.http import HttpRequest, HttpResponse
from ninja_extra import NinjaExtraAPI
from ninja_jwt.authentication import JWTAuth
from ninja_jwt.controller import NinjaJWTDefaultController

from apps.clients.api.v1 import router as clients_router

# Инициализируем API
# NinjaExtraAPI дает больше возможностей, чем просто NinjaAPI
api = NinjaExtraAPI(
    title="Kronon API",
    version="1.0.0",
    description="Enterprise Accounting OS API",
    urls_namespace="api",  # Важно для reverse()
    auth=JWTAuth(),  # JWT по умолчанию для всех эндпоинтов (кроме тех, где auth=None)
)


# --- Подключение контроллеров ---

# Авторизация (получение токена, рефреш)
# Эндпоинты: /api/token/pair, /api/token/refresh, /api/token/verify
api.register_controllers(NinjaJWTDefaultController)


# --- Подключаем роутеры приложений ---

# Клиенты
api.add_router("/clients", clients_router, tags=["Clients"])


# --- Обработка ошибок (Global Exception Handlers) ---


@api.exception_handler(ValueError)
def value_error_handler(request: HttpRequest, exc: ValueError) -> HttpResponse:
    """Перехват ошибок валидации бизнес-логики."""
    return api.create_response(
        request,
        {"message": str(exc), "code": "validation_error"},
        status=400,
    )


@api.exception_handler(Exception)
def internal_server_error_handler(request: HttpRequest, exc: Exception) -> HttpResponse:
    """
    Глобальный перехватчик 500 ошибок.
    В DEBUG режиме Django сам покажет трейсбек, но в проде нельзя его светить.
    """
    # TODO: добавить логгирование в Sentry

    return api.create_response(
        request,
        {"message": "Internal Server Error", "code": "server_error"},
        status=500,
    )
