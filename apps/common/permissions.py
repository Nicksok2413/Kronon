"""
Permissions system for Ninja API endpoints.

RBAC (Role-Based Access Control) и OLP (Object-Level Permissions)
"""

from django.http import HttpRequest
from ninja.errors import HttpError

from apps.clients.models import Client
from apps.common.auth import get_auth_identity
from apps.users.constants import SYSTEM_USER_ID
from apps.users.models import User, UserRole

# ==============================================================================
# BOOLEAN CHECKERS (Бизнес-логика прав, без привязки к HTTP)
# ==============================================================================


def has_admin_access(user: User) -> bool:
    """
    Проверяет, имеет ли пользователь системные (API-ключ) или административные права (RBAC).
    Административные права имеют админ/директор/главбух.
    Работает синхронно, так как объект `user` уже загружен.

    Args:
        user (User): Объект пользователя.

    Returns:
        bool: Флаг наличия системных/административных прав.
    """

    allower_roles = (UserRole.DIRECTOR, UserRole.SYSTEM_ADMINISTRATOR, UserRole.CHIEF_ACCOUNTANT)

    # TODO: подумать не лишняя ли это проверка
    # Если это система, возвращаем True (у системы абсолютные права)
    # Системный юзер и так имеет роль SYSTEM_ADMINISTRATOR (из миграции), но проверяем явно по ID для надежности
    if user.id == SYSTEM_USER_ID:
        return True

    # Если это админ/директор/главбух, возвращаем True
    return user.role in allower_roles


async def has_client_access(user: User, client: Client) -> bool:
    """
    Проверяет, имеет ли пользователь право управлять конкретным клиентом (OLP).

    Логика:
    - Администратор, директор и главбух могут редактировать/удалять всё.
    - Линейный бухгалтер может редактировать только тех клиентов,
       где он указан как ответственный (accountant, primary, payroll, hr).

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


async def enforce_admin_access(request: HttpRequest) -> None:
    """
    Требует права администратора (система/админ/директор/главбух).

    Args:
        request (HttpRequest): Объект HTTP запроса.

    Raises:
        HttpError(403): Если прав нет.
    """
    # Получаем пользователя из запроса
    user = await get_auth_identity(request)

    # Если это не системный/административный доступ - выбрасываем исключение
    if not has_admin_access(user):
        raise HttpError(status_code=403, message="Доступ запрещен. Требуются права администратора.")


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
        raise HttpError(status_code=403, message=f"У вас нет прав на клиента '{client.name}'.") from None
