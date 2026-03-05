"""
Permissions system for Ninja API endpoints.

RBAC (Role-Based Access Control) и OLP (Object-Level Permissions)
"""

from typing import cast

from django.http import HttpRequest
from ninja.errors import HttpError

from apps.clients.models import Client
from apps.common.auth import get_auth_identity
from apps.users.models import User, UserRole


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
    # Идентифицируем личность в запросе (пользователь или система)
    identity = await get_auth_identity(request)

    # Если это система, возвращаем True (у системы абсолютные права)
    if identity == "system_api":
        return True

    # Для JWT-юзеров проверяем права (RBAC)
    user = cast(User, identity)  # Явная типизация для Mypy: в identity лежит User

    # Если это админ/директор/главбух, возвращаем True
    if user.is_staff and user.role in (UserRole.DIRECTOR, UserRole.CHIEF_ACCOUNTANT):
        return True

    # Если это не системный/административный доступ - выбрасываем исключение
    raise HttpError(status_code=403, message="Доступ запрещен. Требуются права администратора.")


async def check_client_access(request: HttpRequest, client: Client) -> None:
    """
    Проверяет, имеет ли текущий пользователь право управлять данным клиентом (OLP).

    Логика:
    1. Администраторы и Директор могут редактировать/удалять всё.
    2. Главный бухгалтер может редактировать всё.
    3. Линейный бухгалтер может редактировать только тех клиентов,
       где он указан как ответственный (accountant, primary, payroll, hr).

    Args:
        request (HttpRequest): Объект входящего запроса.
        client (Client): Экземпляр клиента из БД.

    Raises:
        HttpError(403): Если прав нет.
    """
    try:
        # Если это системный/административный доступ — пропускаем без дальнейших проверок
        await is_admin_access(request)
        return None

    except HttpError:
        # Если нет — проверяем объектные права (OLP)

        # Идентифицируем пользователя
        identity = await get_auth_identity(request)

        user = cast(User, identity)  # Явная типизация для Mypy: в identity лежит User

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
        raise HttpError(status_code=403, message=f"У вас нет прав на клиента '{client.name}'.")
