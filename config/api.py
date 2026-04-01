"""
Root API Configuration.
"""

from ninja_extra import NinjaExtraAPI
from ninja_jwt.authentication import AsyncJWTAuth
from ninja_jwt.controller import NinjaJWTDefaultController

from apps.audit.api.v1.audit import router as audit_v1_router
from apps.clients.api.v1.clients import router as clients_v1_router
from apps.common.auth import AsyncApiKeyAuth
from apps.common.exceptions import setup_exception_handlers
from apps.users.api.v1.directory import router as directory_v1_router

# Инициализируем API
# NinjaExtraAPI дает больше возможностей, чем просто NinjaAPI
api = NinjaExtraAPI(
    title="Kronon API",
    version="1.0.0",
    description="Enterprise Accounting OS API",
    urls_namespace="api",  # Важно для reverse()
    # Аутентификация по умолчанию для всех эндпоинтов
    # Доступ только по JWT и по внутреннему API-Ключу (для межсервисного взаимодействия)
    auth=[AsyncJWTAuth(), AsyncApiKeyAuth()],
)


# --- Подключение контроллеров ---

# Авторизация (получение токена, рефреш)
# Эндпоинты: /api/token/pair, /api/token/refresh, /api/token/verify
api.register_controllers(NinjaJWTDefaultController)


# --- Подключаем роутеры приложений ---

# Audit API (Аудит)
api.add_router("/audit", audit_v1_router)

# Clients API (Клиенты)
api.add_router("/clients", clients_v1_router)

# Users API (Пользователи/Сотрудники)
api.add_router("/directory", directory_v1_router)  # Публичный справочник сотрудников


# --- Подключаем обработчики ошибок ---
setup_exception_handlers(api)
