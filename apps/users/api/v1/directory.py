"""
API Endpoints (v1) для Публичного справочника сотрудников (Directory).

Возвращает только публичные данные (без деталей контрактов).
"""

from typing import Annotated
from uuid import UUID

from django.http import HttpRequest
from loguru import logger as log
from ninja import Query, Router
from ninja.pagination import PageNumberPagination, paginate

from apps.audit.utils import get_initiator_log_str
from apps.common.managers import SoftDeleteQuerySet
from apps.common.schemas import STANDARD_ERRORS
from apps.users.guards import get_employee_or_404
from apps.users.models import User
from apps.users.schemas.directory import UserDirectoryOut
from apps.users.schemas.filters import UserFilter
from apps.users.selectors import get_directory_user_queryset

# Эндпоинты по умолчанию доступны только по JWT и по внутреннему API-Ключу (для межсервисного взаимодействия)
router = Router(tags=["Directory"])


@router.get("/", response={200: list[UserDirectoryOut], **STANDARD_ERRORS})
@paginate(PageNumberPagination, page_size=20)
async def list_directory_users_endpoint(
    request: HttpRequest,
    filters: Annotated[UserFilter, Query(...)],
) -> SoftDeleteQuerySet[User]:
    """
    Получить список всех активных сотрудников (справочник).

    Возвращает только публичные данные (без HR-информации).
    Поддерживает поиск по ФИО, email и фильтрацию по отделам.

    Доступно всем авторизованным пользователям.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        filters (UserFilter): Параметры фильтрации из Query Params.

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(500): Внутренняя ошибка сервера.

    Returns:
        SoftDeleteQuerySet[User]: Отфильтрованный ленивый список сотрудников (пагинация применяется декоратором).
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' requested directory list.")

    # Получаем базовый ленивый QuerySet (только активные юзеры)
    query_set = get_directory_user_queryset()

    # Применяем фильтры из запроса (Query Params): строим SQL-запрос, в БД не идем (Lazy)
    # Ninja.FilterSchema применяет фильтры к QuerySet'у, возвращая новый QuerySet
    query_set = filters.filter(query_set)

    # Возвращаем QuerySet (Ninja применит LIMIT/OFFSET - сделает `aexecute()` с лимитом 20 записей)
    return query_set


@router.get("/{user_id}", response={200: UserDirectoryOut, **STANDARD_ERRORS})
async def get_directory_user_endpoint(request: HttpRequest, user_id: UUID) -> User:
    """
    Получить карточку сотрудника для справочника по ID.

    Доступно всем авторизованным пользователям.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        user_id (UUID): ID сотрудника (UUIDv7).

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(404): Если сотрудник не найден или уволен/неактивен.
        HttpError(500): Внутренняя ошибка сервера.

    Returns:
        User: Объект сотрудника (сериализуется в UserDirectoryOut).
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' requested directory profile for {user_id}.")

    # Находим сотрудника (ищем только среди активных, по умолчанию status="active")
    user = await get_employee_or_404(user_id=user_id)

    # Ninja сам преобразует User в UserDirectoryOut
    return user
