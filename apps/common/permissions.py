"""
Permissions system for Ninja API endpoints.

RBAC (Role-Based Access Control) и OLP (Object-Level Permissions)
"""

from django.http import HttpRequest
from ninja.errors import HttpError

from apps.clients.models.client import Client
from apps.common.auth import get_auth_identity
from apps.users.constants import SYSTEM_USER_ID
from apps.users.models import UserRole


async def is_admin_access(request: HttpRequest) -> bool:
    """
    Проверяет, является ли текущий доступ системным (API-ключ) или административным (админ/директор/главбух).

    Args:
        request (HttpRequest): Объект входящего запроса.

    Raises:
        HttpError(403): Если прав нет.

    Returns:
        bool: Флаг системного/административного доступа.
    """
    # Получаем пользователя из запроса
    user = await get_auth_identity(request)

    # TODO: подумать не лишняя ли это проверка
    # Если это система, возвращаем True (у системы абсолютные права)
    # Системный юзер и так имеет роль SYSTEM_ADMINISTRATOR (из миграции), но проверяем явно по ID для надежности
    if user.id == SYSTEM_USER_ID:
        return True

    # Если это админ/директор/главбух, возвращаем True
    if user.role in (UserRole.DIRECTOR, UserRole.SYSTEM_ADMINISTRATOR, UserRole.CHIEF_ACCOUNTANT):
        return True

    # Если это не системный/административный доступ - выбрасываем исключение
    raise HttpError(status_code=403, message="Доступ запрещен. Требуются права администратора.")


async def check_client_access(request: HttpRequest, client: Client) -> None:
    """
    Проверяет, имеет ли текущий пользователь право управлять данным клиентом (OLP).

    Логика:
    - Администратор, директор и главбух могут редактировать/удалять всё.
    - Линейный бухгалтер может редактировать только тех клиентов,
       где он указан как ответственный (accountant, primary, payroll, hr).

    Args:
        request (HttpRequest): Объект входящего запроса.
        client (Client): Экземпляр клиента из БД.

    Raises:
        HttpError(403): Если прав нет.
    """
    # Проверка на системный/административный доступ (RBAC)
    try:
        # Если да — пропускаем без дальнейших проверок
        await is_admin_access(request)
        return None

    except HttpError:
        # Если нет — проверяем объектные права (OLP)
        user = await get_auth_identity(request)  # Получаем пользователя из запроса

        # Ответственные за этого клиента
        allowed_ids_set = {
            client.accountant_id,
            client.primary_accountant_id,
            client.payroll_accountant_id,
            client.hr_specialist_id,
        }

        # Если пользователь - кто-то из ответственных за этого клиента, пропускаем
        if user.id in allowed_ids_set:
            return None

        # Иначе - выбрасываем исключение
        raise HttpError(status_code=403, message=f"У вас нет прав на клиента '{client.name}'.") from None
