"""
Селекторы (Read Logic) для приложения Users.
Обеспечивают асинхронный и оптимизированный доступ к данным сотрудников.
"""

from typing import Literal, cast
from uuid import UUID

from loguru import logger as log

from apps.common.managers import SoftDeleteQuerySet
from apps.users.models import User


def _get_base_user_queryset(status: Literal["active", "deleted", "all"] = "active") -> SoftDeleteQuerySet[User]:
    """
    Технический метод для оптимизации и сортировки базового "ленивого" (Lazy) QuerySet для списка пользователей.

    Применяет `select_related` для связанных профилей и отделов, избегая N+1.
    Сортирует по убыванию ID (что эквивалентно дате регистрации благодаря UUIDv7).

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

    return cast(
        SoftDeleteQuerySet[User], search_users.select_related("department", "profile").order_by("-id")
    )  # Явная типизация для mypy


def get_directory_user_queryset() -> SoftDeleteQuerySet[User]:
    """
    Возвращает QuerySet активных сотрудников для публичного справочника.
    Возвращаемый QuerySet готов к применению фильтров и пагинации в API.

    Returns:
        SoftDeleteQuerySet[User]: Ленивый (Lazy) QuerySet для публичного справочника сотрудников.
    """
    # Для публичного справочника берем только активных сотрудников (status="active")
    return _get_base_user_queryset(status="active")


def get_internal_hr_user_queryset(status: Literal["active", "deleted", "all"] = "all") -> SoftDeleteQuerySet[User]:
    """
    Возвращает QuerySet сотрудников для внутреннего HR (включает уволенных/неактивных/удаленных по умолчанию).
    Возвращаемый QuerySet готов к применению фильтров и пагинации в API.

    Args:
        status (Literal): Статус записей ("active" - активные, "deleted" - удаленные/неактивные, "all" - все).

    Returns:
        SoftDeleteQuerySet[User]: Ленивый (Lazy) QuerySet сотрудников для внутреннего HR.
    """
    # Для внутреннего HR берем всех сотрудников (status="all")
    return _get_base_user_queryset(status=status)


async def get_user_by_id(user_id: UUID, status: Literal["active", "deleted", "all"] = "active") -> User | None:
    """
    Асинхронно получает детальную информацию о сотруднике по ID с подгруженными связями.

    Args:
        user_id (UUID): ID сотрудника (UUIDv7).
        status (Literal): Флаг поиска (по умолчанию ищет только среди активных).

    Returns:
        User | None: Объект сотруднике или None, если не найден.
    """
    try:
        # Оптимизированный базовый QuerySet
        queryset = _get_base_user_queryset(status=status)

        # .afirst() вместо .aget(), чтобы избежать исключения DoesNotExist и вернуть None
        return await queryset.filter(id=user_id).afirst()

    except Exception as exc:
        log.error(f"DB Error while fetching user {user_id}: {exc}")
        # Глобальный хендлер превратит это в 500
        raise
