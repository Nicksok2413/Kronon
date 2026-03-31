"""
Селекторы (Read Logic) для приложения Users.
Обеспечивают асинхронный и оптимизированный доступ к данным сотрудников.
"""

from typing import Literal
from uuid import UUID

from loguru import logger as log

from apps.common.managers import SoftDeleteQuerySet
from apps.users.models import User


def _get_base_user_queryset(status: Literal["active", "deleted", "all"] = "active") -> SoftDeleteQuerySet[User]:
    """
    Технический метод для оптимизации и сортировки базового "ленивого" (Lazy) QuerySet для списка пользователей.

    Использует select_related для ForeignKey и OneToOneField, чтобы избежать N+1 запросов.
    Гарантирует сортировку по ID (в обратном порядке).

    Args:
        status (Literal): Статус записей ("active" - активные, "deleted" - удаленные/неактивные, "all" - все).

    Returns:
        SoftDeleteQuerySet[User]: Ленивый (Lazy) базовый QuerySet.
    """
    # Логируем на уровне DEBUG, так как это частая операция
    log.debug(f"Building base user queryset (status={status}) with select_related")

    # Формируем QuerySet в зависимости от значения status
    if status == "deleted":
        search_users = User.objects.deleted()
    elif status == "all":
        search_users = User.objects.all()
    else:
        search_users = User.objects.active()

    return search_users.select_related("department", "profile").order_by("-id")


async def get_directory_users() -> list[User]:
    """
    Асинхронно получает список активных сотрудников для публичного справочника.

    Returns:
        list[User]: Список сотрудников.
    """
    log.info("Fetching public directory users list")

    try:
        # Для публичного справочника берем только активных сотрудников (status="active")
        queryset = _get_base_user_queryset(status="active")

        return [user async for user in queryset]

    except Exception as exc:
        log.error(f"DB Error while fetching directory users: {exc}")
        # Глобальный хендлер превратит это в 500
        raise


async def get_hr_users() -> list[User]:
    """
    Асинхронно получает полный список сотрудников (включая уволенных/неактивных) для внутреннего HR.

    Returns:
        list[User]: Список сотрудников.
    """
    log.info("Fetching HR employees list")

    try:
        # Для внутреннего HR берем всех сотрудников (status="all")
        queryset = _get_base_user_queryset(status="all")

        return [user async for user in queryset]

    except Exception as exc:
        log.error(f"DB Error while fetching Internal HR users: {exc}")
        # Глобальный хендлер превратит это в 500
        raise


async def get_user_by_id(user_id: UUID, status: Literal["active", "deleted", "all"] = "active") -> User | None:
    """
    Асинхронно получает пользователя по ID с подгруженными связями.

    Args:
        user_id (UUID): ID сотрудника.
        status (Literal): Статус записей ("active" - активные, "deleted" - удаленные/неактивные, "all" - все).

    Returns:
        User | None: Объект пользователя или None.
    """
    log.debug(f"Fetching user ID: {user_id}")

    try:
        # Оптимизированный базовый QuerySet
        queryset = _get_base_user_queryset(status=status)

        # .afirst() вместо .aget(), чтобы избежать исключения DoesNotExist и вернуть None
        return await queryset.filter(id=user_id).afirst()

    except Exception as exc:
        log.error(f"DB Error while fetching user {user_id}: {exc}")
        # Глобальный хендлер превратит это в 500
        raise
