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
    Проверяет, является ли текущий доступ административным.

    Args:
        request (HttpRequest): Объект входящего запроса.

    Raises:
        HttpError(403): Если прав нет.

    Returns:
        bool: Разрешает доступ админам, директору, главбуху (RBAC) или по системному API Ключу.
    """
    # Идентифицируем личность в запросе (пользователь или система)
    identity = await get_auth_identity(request)

    # Если это система, возвращаем None (у системы абсолютные права)
    if identity == "system_api":
        return True

    # Для JWT-юзеров проверяем права (RBAC)
    user = cast(User, identity)  # Явная типизация для Mypy: в identity лежит User

    # Если это не админ или директор - отказ
    if not user.is_staff and user.role not in (UserRole.DIRECTOR, UserRole.CHIEF_ACCOUNTANT):
        raise HttpError(status_code=403, message="Доступ запрещен. Требуются права администратора.")

    return True


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
    # Идентифицируем личность в запросе (пользователь или система)
    identity = await get_auth_identity(request)

    # Если это система, возвращаем None (у системы абсолютные права)
    if identity == "system_api":
        return None

    # Для JWT-юзеров проверяем права (RBAC)
    user = cast(User, identity)  # Явная типизация для Mypy: в identity лежит User

    # Админы, директор и главбух имеют полный доступ к клиентам
    if user.is_staff or user.role in (UserRole.DIRECTOR, UserRole.CHIEF_ACCOUNTANT):
        return None

    # Если по ролям не прошли, проверяем объектные права (OLP)

    allowed_ids = {
        client.accountant_id,
        client.primary_accountant_id,
        client.payroll_accountant_id,
        client.hr_specialist_id,
    }  # Множество ответственных за этого клиента

    # Если юзер - кто-то из ответственных за этого клиента, пускаем
    if user.id in allowed_ids:
        return None

    # Иначе - отказ
    raise HttpError(status_code=403, message=f"У вас нет прав на клиента '{client.name}'.")
