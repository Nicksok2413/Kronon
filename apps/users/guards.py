"""
Охранные функции (Guards) для приложения Users.
Проверяют существование и права доступа, возвращают объект или выкидывают 404/403.
"""

from typing import Literal
from uuid import UUID

from django.http import HttpRequest
from loguru import logger as log
from ninja.errors import HttpError

from apps.common.permissions import enforce_internal_hr_access
from apps.users.models import User
from apps.users.selectors import get_user_by_id


async def get_employee_or_404(user_id: UUID, status: Literal["active", "deleted", "all"] = "active") -> User:
    """
    Проверяет существование клиента.

    Args:
        user_id (UUID): ID сотрудника (UUIDv7).
        status (Literal): Флаг поиска (по умолчанию ищет только среди активных).

    Raises:
        HttpError(404): Если сотрудника не найден.

    Returns:
        Client: Объект сотрудника.
    """
    # Находим сотрудника, используя селектор для поиска
    user = await get_user_by_id(user_id=user_id, status=status)

    # Проверяем существование сотрудника
    if user:
        log.debug(f"Employee found. Email: {user.email}")
    else:
        log.debug(f"Employee {user_id} not found.")
        raise HttpError(status_code=404, message="Сотрудник не найден.")

    return user


async def get_employee_for_internal_hr_or_404(
    request: HttpRequest,
    user_id: UUID,
) -> User:
    """
    Проверяет права внутреннего HR и существование сотрудника.

    Args:
        request (HttpRequest): Объект входящего запроса.
        user_id (UUID): ID сотрудника (UUIDv7).

    Raises:
        HttpError(403): Если нет прав доступа.
        HttpError(404): Если сотрудник не найден.

    Returns:
        User: Объект сотрудника.
    """
    # Проверка прав (RBAC)
    await enforce_internal_hr_access(request)

    # Находим сотрудника (даже уволенного, чтобы внутренний HR мог его посмотреть)
    user = await get_employee_or_404(user_id=user_id, status="all")

    return user
