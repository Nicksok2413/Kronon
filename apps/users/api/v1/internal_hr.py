"""
API Endpoints (v1) для внутреннего HR (Internal HR).

Управление кадрами самой компании: найм, переводы, увольнения.
Доступно только внутреннему HR и администрации.
"""

from typing import Annotated
from uuid import UUID

from django.http import HttpRequest
from loguru import logger as log
from ninja import Query, Router
from ninja.pagination import PageNumberPagination, paginate

from apps.audit.utils import get_initiator_log_str
from apps.common.managers import SoftDeleteQuerySet
from apps.common.permissions import enforce_internal_hr_access
from apps.common.schemas import STANDARD_ERRORS
from apps.users.guards import get_employee_for_internal_hr_or_404
from apps.users.models import User
from apps.users.schemas.filters import UserFilter
from apps.users.schemas.internal_hr import (
    EmployeeCreate,
    EmployeePrivateOut,
    EmployeeUpdate,
    FireEmployeeIn,
    HireResponseOut,
)
from apps.users.selectors import get_internal_hr_user_queryset
from apps.users.services import fire_employee, hire_employee, update_employee

# Эндпоинты по умолчанию доступны только по JWT и по внутреннему API-Ключу (для межсервисного взаимодействия)
router = Router(tags=["Internal HR"])


@router.get("/", response={200: list[EmployeePrivateOut], **STANDARD_ERRORS})
@paginate(PageNumberPagination, page_size=20)
async def list_employees_endpoint(
    request: HttpRequest,
    filters: Annotated[UserFilter, Query(...)],
) -> SoftDeleteQuerySet[User]:
    """
    Получить полный список сотрудников (включая уволенных).
    Для HR-панели (с отображением контрактов и статусов).
    Поддерживает поиск по ФИО, email и фильтрацию по отделам.

    Доступно системе, администраторам и внутреннему HR.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        filters (UserFilter): Параметры фильтрации из Query Params.

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Доступ запрещен (RBAC).
        HttpError(500): Внутренняя ошибка сервера.

    Returns:
        SoftDeleteQuerySet[User]: Отфильтрованный ленивый список сотрудников (пагинация применяется декоратором).
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' requested employees list.")

    # Проверяем права внутреннего HR (RBAC)
    await enforce_internal_hr_access(request)

    # Получаем ленивый QuerySet (status="all", чтобы видеть уволенных)
    query_set = get_internal_hr_user_queryset(status="all")

    # Применяем фильтры из запроса (Query Params): строим SQL-запрос, в БД не идем (Lazy)
    # Ninja.FilterSchema применяет фильтры к QuerySet'у, возвращая новый QuerySet
    query_set = filters.filter(query_set)

    # Возвращаем QuerySet (Ninja применит LIMIT/OFFSET - сделает `aexecute()` с лимитом 20 записей)
    return query_set


@router.get("/{client_id}", response={200: EmployeePrivateOut, **STANDARD_ERRORS})
async def get_employee_endpoint(request: HttpRequest, user_id: UUID) -> User:
    """
    Получить детальную информацию о сотруднике по ID.

    Доступно системе, администраторам и внутреннему HR.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        user_id (UUID): ID сотрудника (UUIDv7).

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Доступ запрещен (RBAC).
        HttpError(404): Если сотрудник не найден.
        HttpError(500): Внутренняя ошибка сервера.

    Returns:
        User: Объект сотрудника (сериализуется в EmployeePrivateOut).
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' requested private profile for {user_id}.")

    # Проверяем права (RBAC) и существование сотрудника
    user = await get_employee_for_internal_hr_or_404(request=request, user_id=user_id)

    # Ninja сам преобразует User в EmployeePrivateOut
    return user


@router.post("/", response={201: HireResponseOut, **STANDARD_ERRORS})
async def hire_employee_endpoint(request: HttpRequest, payload: EmployeeCreate) -> tuple[int, dict[str, User | str]]:
    """
    Нанять нового сотрудника.
    Создает аккаунт и генерирует временный пароль для первого входа.

    Доступно системе, администраторам и внутреннему HR.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        payload (EmployeeCreate): Данные для создания.

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Доступ запрещен (RBAC).
        HttpError(409): Конфликт (например, дубликат email).
        HttpError(422): Ошибка структуры передаваемых данных.
        HttpError(500): Внутренняя ошибка сервера.

    Returns:
        tuple[int, dict[str, User | str]]: Код ответа, словарь с созданным объектом сотрудника и временным паролем.
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' attempts to hire employee '{payload.email}'.")

    # Проверяем права внутреннего HR (RBAC)
    await enforce_internal_hr_access(request)

    # Вызываем сервис создания
    user, temporary_password = await hire_employee(data=payload, audit_context=audit_context)

    # Возвращаем статус код, созданного пользователя и временный пароль
    return 201, {"employee": user, "temporary_password": temporary_password}


@router.patch("/{user_id}", response={200: EmployeePrivateOut, **STANDARD_ERRORS})
async def update_employee_endpoint(request: HttpRequest, user_id: UUID, payload: EmployeeUpdate) -> User:
    """
    Изменить кадровые данные сотрудника (перевод, продление контракта).

    Доступно системе, администраторам и внутреннему HR.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        user_id (UUID): ID сотрудника (UUIDv7).
        payload (EmployeeUpdate): Данные для обновления.

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Доступ запрещен (RBAC).
        HttpError(404): Если сотрудник не найден.
        HttpError(422): Ошибка структуры передаваемых данных.
        HttpError(500): Внутренняя ошибка сервера.

    Returns:
        Client: Обновленный объект клиента (сериализуется в ClientOut).
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' attempts to update employee {user_id}.")

    # Проверяем права (RBAC) и существование сотрудника
    user = await get_employee_for_internal_hr_or_404(request=request, user_id=user_id)

    # Вызываем сервис обновления
    updated_user = await update_employee(user=user, data=payload, audit_context=audit_context)

    # Возвращаем обновленного сотрудника
    return updated_user


@router.delete("/{user_id}", response={204: None, **STANDARD_ERRORS})
async def fire_employee_endpoint(request: HttpRequest, user_id: UUID, payload: FireEmployeeIn) -> tuple[int, None]:
    """
    Уволить сотрудника (Soft Delete).
    Блокирует доступ к системе.
    Опционально передает всех клиентов преемнику.

    Доступно системе, администраторам и внутреннему HR.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        user_id (UUID): ID сотрудника (UUIDv7).
        payload (FireEmployeeIn): ID сотрудника, которому будут переданы все клиенты увольняемого или None.

    Raises:
        HttpError(400): Ошибка бизнес-логики.
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Доступ запрещен (RBAC).
        HttpError(404): Если сотрудник не найден.
        HttpError(500): Внутренняя ошибка сервера.

    Returns:
        tuple[int, None]: Код ответа 204 (No Content), None
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' attempts to fire employee {user_id}.")

    # Проверяем права (RBAC) и существование сотрудника
    user = await get_employee_for_internal_hr_or_404(request=request, user_id=user_id)

    # Вызываем сервис увольнения
    # Сервис может кинуть ValueError (например, преемник не найден)
    # Глобальный value_error_handler превратит это в 400 Bad Request
    await fire_employee(user=user, data=payload, audit_context=audit_context)

    # Возвращаем код ответа
    return 204, None
