"""
Система разрешений (Permissions System) для эндпоинтов Ninja API.
RBAC (Role-Based Access Control) и OLP (Object-Level Permissions).

Основана на паттерне "Checkers & Enforcers":
- Checkers (has_*): чистые функции, возвращают bool. Удобны для тестов.
- Enforcers (enforce_*): асинхронные функции для роутеров, выбрасывают HttpError.
"""

from django.conf import settings
from django.http import HttpRequest
from loguru import logger as log
from ninja.errors import HttpError

from apps.audit.utils import get_ip_address
from apps.clients.models import Client
from apps.common.auth import get_auth_identity
from apps.users.constants import SYSTEM_USER_ID
from apps.users.models import User, UserRole

# ==============================================================================
# BOOLEAN CHECKERS (Бизнес-логика прав, без привязки к HTTP)
# ==============================================================================


def has_system_access(user: User) -> bool:
    """
    Проверяет, имеет ли пользователь системные (полные) права.
    Системные права имеют системный пользователь (SYSTEM_USER_ID) и системные администраторы.
    Работает синхронно, так как объект `user` уже загружен.

    Args:
        user (User): Объект пользователя.

    Returns:
        bool: Флаг наличия системных прав.
    """
    return user.id == SYSTEM_USER_ID or user.role == UserRole.SYSTEM_ADMINISTRATOR


def has_admin_access(user: User) -> bool:
    """
    Проверяет, имеет ли пользователь административные права.
    Административные права имеют директор/главбух.
    Работает синхронно, так как объект `user` уже загружен.

    Args:
        user (User): Объект пользователя.

    Returns:
        bool: Флаг наличия административных прав.
    """

    # Проверяем на системные права
    if has_system_access(user):
        # Если права есть — пропускаем без дальнейших проверок
        return True

    return user.role in (UserRole.DIRECTOR, UserRole.CHIEF_ACCOUNTANT)


def has_internal_hr_access(user: User) -> bool:
    """
    Проверяет, имеет ли пользователь права внутреннего HR-специалиста.
    Работает синхронно, так как объект `user` уже загружен.

    Args:
        user (User): Объект пользователя.

    Returns:
        bool: Флаг наличия прав внутреннего HR-специалиста.
    """
    # Проверяем на административные права
    if has_admin_access(user):
        # Если права есть — пропускаем без дальнейших проверок
        return True

    return user.role == UserRole.HR


def has_client_access(user: User, client: Client) -> bool:
    """
    Проверяет, имеет ли пользователь право управлять конкретным клиентом (OLP).
    Работает синхронно, так как объект `user` и `client` уже загружены.

    Логика:
    - Пользователи с системными/административными правами могут редактировать/удалять всех клиентов.
    - Линейный бухгалтер может редактировать только тех клиентов, где он указан как ответственный.

    Args:
        user (User): Объект пользователя.
        client (Client): Объект клиента.

    Returns:
        bool: Флаг наличия объектных прав.
    """
    # --- Проверяем на системные/административные права (RBAC) ---
    if has_admin_access(user):
        # Если права есть — пропускаем без дальнейших проверок
        return True

    # --- Проверяем объектные права (OLP) ---

    # Ответственные за этого клиента
    allowed_ids_set = {
        client.accountant_id,
        client.primary_accountant_id,
        client.payroll_accountant_id,
        client.hr_specialist_id,
    }

    # Если пользователь - кто-то из ответственных за этого клиента, возвращаем True
    return user.id in allowed_ids_set


# ==============================================================================
# ENFORCERS (Функции для вызова в эндпоинтах API)
# ==============================================================================


def enforce_api_key(request: HttpRequest) -> None:
    """
    Проверяет статический API-ключ (для M2M интеграций, если понадобятся).
    Работает синхронно (не требует БД).

    Args:
        request (HttpRequest): Объект HTTP запроса.

    Raises:
        HttpError(403): Если прав нет.
    """
    api_key = request.headers.get("X-API-Key")
    expected_key = getattr(settings, "INTERNAL_API_KEY", None)

    # Если ключа в заголовках нет или он не совпадает - выбрасываем исключение
    if not expected_key or api_key != expected_key:
        ip_address = get_ip_address(request)
        log.warning(f"Invalid API Key attempt from {ip_address}")
        raise HttpError(status_code=403, message="Недействительный API-ключ.")


async def enforce_admin_access(request: HttpRequest) -> None:
    """
    Требует административные права.

    Args:
        request (HttpRequest): Объект HTTP запроса.

    Raises:
        HttpError(403): Если прав нет.
    """
    # Получаем пользователя из запроса
    user = await get_auth_identity(request)

    # Если это не системный/административный доступ - выбрасываем исключение
    if not has_admin_access(user):
        log.warning(f"Access denied (Admin required) for user {user.id}")
        raise HttpError(status_code=403, message="Доступ запрещен. Требуются права администратора.")


async def enforce_internal_hr_access(request: HttpRequest) -> None:
    """
    Требует права внутреннего HR-специалиста.

    Args:
        request (HttpRequest): Объект HTTP запроса.

    Raises:
        HttpError(403): Если прав нет.
    """
    # Получаем пользователя из запроса
    user = await get_auth_identity(request)

    # Если это не внутренний HR-специалист - выбрасываем исключение
    if not has_internal_hr_access(user):
        log.warning(f"Access denied (Internal HR required) for user {user.id}")
        raise HttpError(status_code=403, message="Доступ запрещен. Требуются права внутреннего HR.")


async def enforce_client_access(request: HttpRequest, client: Client) -> None:
    """
    Требует права на управление конкретным клиентом.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        client (Client): Экземпляр клиента из БД.

    Raises:
        HttpError(403): Если прав нет.
    """
    # Получаем пользователя из запроса
    user = await get_auth_identity(request)

    # Если пользователь не из ответственных за этого клиента - выбрасываем исключение
    if not has_client_access(user=user, client=client):
        log.warning(f"Access denied (Forbidden) for user {user.id}")
        raise HttpError(status_code=403, message=f"У вас нет прав на клиента '{client.name}'.") from None
