"""
Root API Configuration.
"""

from ninja_extra import NinjaExtraAPI
from ninja_jwt.authentication import AsyncJWTAuth
from ninja_jwt.controller import NinjaJWTDefaultController

from apps.clients.api.v1 import router as clients_router
from apps.common.exceptions import setup_exception_handlers

# Инициализируем API
# NinjaExtraAPI дает больше возможностей, чем просто NinjaAPI
api = NinjaExtraAPI(
    title="Kronon API",
    version="1.0.0",
    description="Enterprise Accounting OS API",
    urls_namespace="api",  # Важно для reverse()
    auth=AsyncJWTAuth(),  # JWT по умолчанию для всех эндпоинтов (кроме тех, где auth=None)
)


# --- Подключение контроллеров ---

# Авторизация (получение токена, рефреш)
# Эндпоинты: /api/token/pair, /api/token/refresh, /api/token/verify
api.register_controllers(NinjaJWTDefaultController)


# --- Подключаем роутеры приложений ---

# Клиенты
api.add_router("/clients", clients_router, tags=["Clients"])


# --- Подключаем обработчики ошибок ---
setup_exception_handlers(api)
