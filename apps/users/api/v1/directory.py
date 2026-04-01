"""
API Endpoints для Публичного справочника сотрудников (Directory).

Доступно всем авторизованным пользователям.
Возвращает только публичные данные (без деталей контрактов).
"""

from typing import Annotated
from uuid import UUID

from django.http import HttpRequest
from loguru import logger as log
from ninja import Query, Router
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate

from apps.common.managers import SoftDeleteQuerySet
from apps.common.schemas import STANDARD_ERRORS
from apps.users.models import User
from apps.users.schemas.directory import UserDirectoryOut
from apps.users.schemas.filters import UserFilter
from apps.users.selectors import get_directory_user_queryset, get_user_by_id

# Эндпоинты по умолчанию доступны только по JWT и по внутреннему API-Ключу (для межсервисного взаимодействия)
router = Router(tags=["Directory"])


@router.get("/", response={200: list[UserDirectoryOut], **STANDARD_ERRORS})
@paginate(PageNumberPagination, page_size=20)
async def list_directory_users(
    request: HttpRequest,
    filters: Annotated[UserFilter, Query(...)],
) -> SoftDeleteQuerySet[User]:
    """
    Получить список всех активных сотрудников (справочник).
    Доступно всем авторизованным пользователям.

    Возвращает только публичные данные (без HR-информации).
    Поддерживает поиск по ФИО, email и фильтрацию по отделам.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        filters (UserFilter): Параметры фильтрации из Query Params.

    Returns:
        SoftDeleteQuerySet[User]: Отфильтрованный ленивый список сотрудников (пагинация применяется декоратором).
    """
    log.info(f"User {request.user.id} requested directory list.")

    # Получаем базовый ленивый QuerySet (только активные юзеры)
    query_set = get_directory_user_queryset()

    # Применяем фильтры из запроса (Query Params): строим SQL-запрос, в БД не идем (Lazy)
    # Ninja.FilterSchema применяет фильтры к QuerySet'у, возвращая новый QuerySet
    query_set = filters.filter(query_set)

    # Возвращаем QuerySet (Ninja применит LIMIT/OFFSET - сделает `aexecute()` с лимитом 20 записей)
    return query_set


@router.get("/{user_id}", response={200: UserDirectoryOut, **STANDARD_ERRORS})
async def get_directory_user(request: HttpRequest, user_id: UUID) -> User:
    """
    Получить карточку сотрудника для справочника по ID.
    Доступно всем авторизованным пользователям.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        user_id (UUID): ID сотрудника (UUIDv7).

    Raises:
        HttpError(404): Если сотрудник не найден или уволен/неактивен.

    Returns:
        User: Объект сотрудника (сериализуется в UserDirectoryOut).
    """
    log.info(f"User {request.user.id} requested directory profile for {user_id}.")

    # Находим сотрудника (ищем только среди активных)
    user = await get_user_by_id(user_id=user_id, status="active")

    # Проверяем существование сотрудника
    if user:
        log.debug(f"User found. Email: {user.email}")
    else:
        log.debug(f"User {user_id} not found.")
        raise HttpError(status_code=404, message="Сотрудник не найден.")

    # Ninja сам преобразует User в UserDirectoryOut
    return user
