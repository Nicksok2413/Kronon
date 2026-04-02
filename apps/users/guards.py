"""
Охранные функции (Guards) для приложения Users.
Проверяют существование и права доступа, возвращают объект или выкидывают 404/403.
"""

from uuid import UUID

from django.http import HttpRequest
from loguru import logger as log
from ninja.errors import HttpError

from apps.common.permissions import enforce_internal_hr_access
from apps.users.models import User
from apps.users.selectors import get_user_by_id


async def get_employee_for_internal_hr_or_404(request: HttpRequest, user_id: UUID) -> User:
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
    user = await get_user_by_id(user_id=user_id, status="all")

    # Проверяем существование сотрудника
    if user:
        log.debug(f"Employee found. Email: {user.email}, Active: {user.is_active}")
    else:
        log.warning(f"Employee {user_id} not found.")
        raise HttpError(404, "Сотрудник не найден.")

    return user
