"""
API Endpoints для Клиентов (v1).

Предоставляет методы для чтения (GET), создания (POST), обновления (PATCH) и удаления (DELETE) клиентов.
"""

from typing import Annotated
from uuid import UUID

from django.http import HttpRequest
from loguru import logger as log
from ninja import Query, Router
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate
from ninja_jwt.authentication import AsyncJWTAuth

from apps.clients.guards import get_client_for_admin_or_404, get_client_for_edit_or_404
from apps.clients.models import Client
from apps.clients.schemas.client import ClientCreate, ClientOut, ClientUpdate
from apps.clients.schemas.filters import ClientFilter
from apps.clients.selectors import get_client_queryset
from apps.clients.services import create_client, delete_client, restore_client, update_client
from apps.common.auth import AsyncApiKeyAuth, get_request_initiator
from apps.common.managers import SoftDeleteQuerySet
from apps.common.permissions import is_admin_access
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
    # Получаем инициатора запроса (id для аудита, str для логов)
    initiator_id, initiator_str = await get_request_initiator(request)

    log.info(f"Initiator '{initiator_str}' fetching clients list.")

    # Проверяем права (RBAC) без рейза ошибки, просто для фильтрации
    try:
        is_admin = await is_admin_access(request)
    except HttpError:
        is_admin = False

    # Получаем базовый QuerySet (Lazy) с OLP-фильтрацией на уровне БД
    query_set = get_client_queryset(user_id=initiator_id, is_admin=is_admin)

    # Применяем фильтры из запроса: строим SQL-запрос, в БД не идем (Lazy)
    # Ninja.FilterSchema применяет фильтры к QuerySet'у, возвращая новый QuerySet
    query_set = filters.filter(query_set)

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
    # Получаем инициатора запроса (id для аудита, str для логов)
    initiator_id, initiator_str = await get_request_initiator(request)

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
    # Получаем инициатора запроса (id для аудита, str для логов)
    initiator_id, initiator_str = await get_request_initiator(request)

    log.info(f"Initiator '{initiator_str}' attempts to create client '{payload.name}'.")

    # Проверяем права (RBAC)
    await is_admin_access(request)

    # Вызываем сервис создания
    client = await create_client(data=payload, initiator=initiator_id)

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
    # Получаем инициатора запроса (id для аудита, str для логов)
    initiator_id, initiator_str = await get_request_initiator(request)

    log.info(f"Initiator '{initiator_str}' attempts to update client {client_id}.")

    # Проверяем существование клиента и права (RBAC + OLP)
    client = await get_client_for_edit_or_404(request=request, client_id=client_id)

    # Вызываем сервис обновления
    updated_client = await update_client(client=client, data=payload, initiator=initiator_id)

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
    # Получаем инициатора запроса (id для аудита, str для логов)
    initiator_id, initiator_str = await get_request_initiator(request)

    log.info(f"Initiator '{initiator_str}' attempts to delete client {client_id}.")

    # Проверяем существование клиента и права (RBAC)
    client = await get_client_for_admin_or_404(request=request, client_id=client_id)

    # Вызываем сервис удаления
    await delete_client(client=client, initiator=initiator_id)

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
    # Получаем инициатора запроса (id для аудита, str для логов)
    initiator_id, initiator_str = await get_request_initiator(request)

    log.info(f"Initiator '{initiator_str}' attempts to restore client {client_id}.")

    # Проверяем существование клиента и права (RBAC)
    client = await get_client_for_admin_or_404(request=request, client_id=client_id, is_deleted=True)

    # Вызываем сервис восстановления
    restored_client = await restore_client(client=client, initiator=initiator_id)

    # Возвращаем восстановленного клиента
    return restored_client
