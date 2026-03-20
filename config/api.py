"""
Root API Configuration.
"""

from ninja_extra import NinjaExtraAPI
from ninja_jwt.authentication import AsyncJWTAuth
from ninja_jwt.controller import NinjaJWTDefaultController

from apps.audit.api.v1 import router as audit_router
from apps.clients.api.v1 import router as clients_router
from apps.common.auth import AsyncApiKeyAuth
from apps.common.exceptions import setup_exception_handlers

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
