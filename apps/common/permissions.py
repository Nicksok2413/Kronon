"""
Permissions system for Ninja API endpoints.

RBAC (Role-Based Access Control) и OLP (Object-Level Permissions)
"""

from django.http import HttpRequest
from ninja.errors import HttpError

from apps.clients.models import Client
from apps.users.models import UserRole


async def require_admin(request: HttpRequest) -> None:
    """
    Разрешает доступ только Директору, Staff (RBAC) или Системному API Ключу.

    Args:
        request (HttpRequest): Объект входящего запроса.

    Raises:
        HttpError(403): Если прав нет.
    """
    # Если авторизация по API-ключу, у системы абсолютные права
    if request.auth == "system_api":
        return None

    # Для обычных JWT пользователей
    user = await request.auser()

    if not user.is_staff and user.role != UserRole.DIRECTOR:
        raise HttpError(status_code=403, message="Доступ запрещен. Требуются права администратора.")

    return None


async def check_client_access(request: HttpRequest, client: Client) -> None:
    """
    Проверяет, имеет ли текущий пользователь право управлять данным клиентом (OLP).

    Логика:
    1. Администраторы и Директора могут редактировать/удалять всё.
    2. Главный бухгалтер может редактировать всё.
    3. Линейный бухгалтер может редактировать только тех клиентов,
       где он указан как ответственный (accountant, primary, payroll, hr).

    Args:
        request (HttpRequest): Объект входящего запроса.
        client (Client): Экземпляр клиента из БД.

    Raises:
        HttpError(403): Если прав нет.
    """
    # Если авторизация по API-ключу, у системы абсолютные права
    if request.auth == "system_api":
        return None

    # Для обычных JWT пользователей
    user = await request.auser()

    # Суперпользователи, директора и главбухи имеют полный доступ к клиентам
    if user.is_staff or user.role in (UserRole.DIRECTOR, UserRole.CHIEF_ACCOUNTANT):
        return None

    # Проверяем объектные права (связи)
    # Если юзер - кто-то из ответственных за этого клиента, пускаем
    allowed_users = [
        client.accountant_id,
        client.primary_accountant_id,
        client.payroll_accountant_id,
        client.hr_specialist_id,
    ]

    if user.id in allowed_users:
        return None

    # Иначе - отказ
    raise HttpError(status_code=403, message=f"У вас нет прав на редактирование клиента {client.name}.")
