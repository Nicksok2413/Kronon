"""
API Endpoints (v1) для внутреннего HR (Internal HR).

Управление кадрами самой компании: найм, переводы, увольнения.
Доступно только внутреннему HR и администрации.
"""

from typing import Annotated
from uuid import UUID

from django.db import IntegrityError
from django.http import HttpRequest
from loguru import logger as log
from ninja import Query, Router
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate

from apps.audit.utils import get_initiator_log_str
from apps.common.managers import SoftDeleteQuerySet
from apps.common.permissions import enforce_internal_hr_access
from apps.common.schemas import STANDARD_ERRORS
from apps.users.models import User
from apps.users.schemas.filters import UserFilter
from apps.users.schemas.internal_hr import (
    EmployeeCreate,
    EmployeePrivateOut,
    EmployeeUpdate,
    FireEmployeeIn,
    HireResponseOut,
)
from apps.users.selectors import get_internal_hr_user_queryset, get_user_by_id
from apps.users.services import fire_employee, hire_employee, update_employee

# Эндпоинты по умолчанию доступны только по JWT и по внутреннему API-Ключу (для межсервисного взаимодействия)
router = Router(tags=["Internal HR"])


@router.get("/", response={200: list[EmployeePrivateOut], **STANDARD_ERRORS})
@paginate(PageNumberPagination, page_size=20)
async def list_employees(
    request: HttpRequest,
    filters: Annotated[UserFilter, Query(...)],
) -> SoftDeleteQuerySet[User]:
    """
    Получить полный список сотрудников (включая уволенных).
    Для HR-панели (с отображением контрактов и статусов).
    """
    await enforce_internal_hr_access(request)

    # Получаем ленивый QuerySet (status="all", чтобы видеть уволенных)
    query_set = get_internal_hr_user_queryset(status="all")
    query_set = filters.filter(query_set)
    return query_set


@router.post("/", response={201: HireResponseOut, **STANDARD_ERRORS})
async def hire_employee_endpoint(request: HttpRequest, payload: EmployeeCreate):
    """
    Нанять нового сотрудника.
    Создает аккаунт и генерирует временный пароль для первого входа.
    """
    await enforce_internal_hr_access(request)
    audit_context = getattr(request, "audit_context", {})
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' attempts to hire {payload.email}.")

    try:
        user, temp_password = await hire_employee(data=payload, audit_context=audit_context)
    except IntegrityError:
        # Перехватываем уникальность Email (на уровне БД)
        raise HttpError(409, f"Сотрудник с email {payload.email} уже существует.") from None

    # Возвращаем пользователя и сгенерированный пароль
    return 201, {"employee": user, "temporary_password": temp_password}


@router.patch("/{user_id}", response={200: EmployeePrivateOut, **STANDARD_ERRORS})
async def update_employee_endpoint(request: HttpRequest, user_id: UUID, payload: EmployeeUpdate) -> User:
    """
    Изменить кадровые данные сотрудника (перевод, продление контракта).
    """
    await enforce_internal_hr_access(request)
    audit_context = getattr(request, "audit_context", {})

    user = await get_user_by_id(user_id=user_id, status="all")
    if not user:
        raise HttpError(404, "Сотрудник не найден.")

    updated_user = await update_employee(user=user, data=payload, audit_context=audit_context)
    return updated_user


@router.delete("/{user_id}", response={204: None, **STANDARD_ERRORS})
async def fire_employee_endpoint(request: HttpRequest, user_id: UUID, payload: FireEmployeeIn):
    """
    Уволить сотрудника (Soft Delete).
    Блокирует доступ к системе. Опционально передает всех клиентов преемнику.
    """
    await enforce_internal_hr_access(request)
    audit_context = getattr(request, "audit_context", {})
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' attempts to fire {user_id}.")

    # Уволить можно только активного сотрудника
    user = await get_user_by_id(user_id=user_id, status="active")
    if not user:
        raise HttpError(404, "Сотрудник не найден или уже уволен.")

    if user.id == request.user.id:
        raise HttpError(400, "Вы не можете уволить сами себя через API.")

    # Сервис может кинуть ValueError (например, преемник не найден)
    # Глобальный value_error_handler превратит это в 400 Bad Request
    await fire_employee(user=user, payload=payload, audit_context=audit_context)

    return 204, None
