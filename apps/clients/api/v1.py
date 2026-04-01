"""
API Endpoints для Клиентов (v1).

Предоставляет методы для чтения (GET), создания (POST), обновления (PATCH) и удаления (DELETE) клиентов.
"""

from typing import Annotated
from uuid import UUID

from django.http import HttpRequest
from loguru import logger as log
from ninja import Query, Router
from ninja.pagination import PageNumberPagination, paginate
from ninja_jwt.authentication import AsyncJWTAuth

from apps.audit.utils import get_initiator_log_str
from apps.clients.guards import get_client_for_admin_or_404, get_client_for_edit_or_404
from apps.clients.models import Client
from apps.clients.schemas.client import ClientCreate, ClientOut, ClientUpdate
from apps.clients.schemas.filters import ClientFilter
from apps.clients.selectors import get_client_queryset
from apps.clients.services import create_client, delete_client, restore_client, update_client
from apps.common.auth import AsyncApiKeyAuth, get_auth_identity
from apps.common.managers import SoftDeleteQuerySet
from apps.common.permissions import enforce_admin_access, has_admin_access
from apps.common.schemas import STANDARD_ERRORS

# Эндпоинты доступны как по JWT, так и по API Ключу (для скриптов)
router = Router(auth=[AsyncJWTAuth(), AsyncApiKeyAuth()])


@router.get("/", response={200: list[ClientOut], **STANDARD_ERRORS})
@paginate(PageNumberPagination, page_size=20)
async def list_clients(
    request: HttpRequest,
    filters: Annotated[ClientFilter, Query(...)],
) -> SoftDeleteQuerySet[Client]:
    """
    Получить список клиентов с нативной OLP-фильтрацией, фильтрацией из запроса и пагинацией.
    Доступно системе, администраторам и ответственным лицам.

    Args:
        request (HttpRequest): Объект входящего HTTP запроса.
        filters (ClientFilter): Параметры фильтрации из Query Params.

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(500): Внутренняя ошибка сервера.

    Returns:
        SoftDeleteQuerySet[Client]: Отфильтрованный список клиентов (пагинация применяется декоратором).
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' fetching clients list.")

    # Получаем юзера из запроса
    user = await get_auth_identity(request)

    # Проверяем административные права (через чекер, без рейза) для флага фильтрации
    is_admin = has_admin_access(user)

    # Получаем базовый QuerySet (Lazy) с OLP-фильтрацией на уровне БД
    query_set = get_client_queryset(user_id=user.id, is_admin=is_admin, status="active")

    # Применяем фильтры из запроса: строим SQL-запрос, в БД не идем (Lazy)
    # Ninja.FilterSchema применяет фильтры к QuerySet'у, возвращая новый QuerySet
    query_set = filters.filter(query_set)

    # Возвращаем QuerySet (Ninja сделает `aexecute()` с лимитом 20 записей)
    return query_set


@router.get("/{client_id}", response={200: ClientOut, **STANDARD_ERRORS})
async def get_client(request: HttpRequest, client_id: UUID) -> Client:
    """
    Получить детальную информацию о клиенте по ID.
    Доступно системе, администраторам и ответственным лицам.

    Args:
        request (HttpRequest): Объект входящего HTTP запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Нет прав на просмотр данного клиента.
        HttpError(404): Если клиент не найден.

    Returns:
        Client: Объект клиента.
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' requesting client {client_id}.")

    # Проверяем существование клиента и права (RBAC + OLP)
    client = await get_client_for_edit_or_404(request=request, client_id=client_id)

    # Ninja сам преобразует Client в ClientOut
    return client


@router.post("/", response={201: ClientOut, **STANDARD_ERRORS})
async def create_client_endpoint(request: HttpRequest, payload: ClientCreate) -> tuple[int, Client]:
    """
    Создание нового клиента.
    Доступно только системе и администраторам.

    Args:
        request (HttpRequest): Объект входящего HTTP запроса.
        payload (ClientCreate): Данные для создания.

    Raises:
        HttpError(400): Ошибка бизнес-логики.
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Доступ запрещен (требуются права администратора).
        HttpError(409): Конфликт (например, дубликат УНП).
        HttpError(422): Ошибка структуры передаваемых данных.

    Returns:
        tuple[int, Client]: Код ответа, созданный объект клиента.
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' attempts to create client '{payload.name}'.")

    # Проверяем административные права (RBAC)
    await enforce_admin_access(request)

    # Вызываем сервис создания
    client = await create_client(data=payload, audit_context=audit_context)

    # Возвращаем созданного клиента
    return 201, client


@router.patch("/{client_id}", response={200: ClientOut, **STANDARD_ERRORS})
async def update_client_endpoint(request: HttpRequest, client_id: UUID, payload: ClientUpdate) -> Client:
    """
    Частичное обновление данных клиента.
    Доступно системе, администраторам и ответственным лицам.

    Args:
        request (HttpRequest): Объект входящего HTTP запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).
        payload (ClientUpdate): Данные для обновления.

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Нет прав на редактирование данного клиента.
        HttpError(404): Если клиент не найден.
        HttpError(409): Конфликт данных (например, дубликат УНП).
        HttpError(422): Ошибка структуры передаваемых данных.

    Returns:
        Client: Обновленный объект клиента.
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' attempts to update client {client_id}.")

    # Проверяем существование клиента и права (RBAC + OLP)
    client = await get_client_for_edit_or_404(request=request, client_id=client_id)

    # Вызываем сервис обновления
    updated_client = await update_client(client=client, data=payload, audit_context=audit_context)

    # Возвращаем обновленного клиента
    return updated_client


@router.delete("/{client_id}", response={204: None, **STANDARD_ERRORS})
async def delete_client_endpoint(request: HttpRequest, client_id: UUID) -> tuple[int, None]:
    """
    Мягкое удаление (Soft Delete) клиента.

    Клиент скрывается из списков, но остается в БД.
    Доступно только системе и администраторам.

    Args:
        request (HttpRequest): Объект входящего HTTP запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Доступ запрещен (требуются права администратора).
        HttpError(404): Если клиент не найден.

    Returns:
        tuple[int, None]: Код ответа 204 (No Content), None
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' attempts to delete client {client_id}.")

    # Проверяем существование клиента и права (RBAC)
    client = await get_client_for_admin_or_404(request=request, client_id=client_id)

    # Вызываем сервис удаления
    await delete_client(client=client, audit_context=audit_context)

    # Возвращаем код ответа
    return 204, None


@router.patch("/{client_id}/restore", response={200: ClientOut, **STANDARD_ERRORS})
async def restore_client_endpoint(request: HttpRequest, client_id: UUID) -> Client:
    """
    Восстановление клиента после мягкого удаления.
    Доступно только системе и администраторам.

    Args:
        request (HttpRequest): Объект входящего HTTP запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Нет прав на редактирование данного клиента.
        HttpError(404): Если клиент не найден.

    Returns:
        Client: Восстановленный объект клиента.
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' attempts to restore client {client_id}.")

    # Проверяем существование клиента и права (RBAC)
    client = await get_client_for_admin_or_404(request=request, client_id=client_id, status="deleted")

    # Вызываем сервис восстановления
    restored_client = await restore_client(client=client, audit_context=audit_context)

    # Возвращаем восстановленного клиента
    return restored_client
