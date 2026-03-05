"""
API Endpoints для Клиентов (v1).

Предоставляет методы для чтения (GET), создания (POST), обновления (PATCH)
и удаления (DELETE) клиентов. А так же историю изменения клиентов (GET).
"""

from typing import Annotated, Any
from uuid import UUID

from django.http import HttpRequest
from loguru import logger as log
from ninja import Query, Router
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate
from ninja_jwt.authentication import AsyncJWTAuth

from apps.clients.models import Client
from apps.clients.schemas.client import ClientCreate, ClientOut, ClientUpdate
from apps.clients.schemas.filters import ClientFilter
from apps.clients.schemas.history import ClientHistoryOut
from apps.clients.selectors import get_client_by_id, get_client_history_queryset, get_client_queryset
from apps.clients.services import create_client, delete_client, update_client
from apps.common.auth import AsyncApiKeyAuth, get_request_initiator
from apps.common.managers import SoftDeleteQuerySet
from apps.common.permissions import check_client_access, is_admin_access
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

    Args:
        request (HttpRequest): Объект входящего запроса.
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

    # Проверяем роли (RBAC) без рейза ошибки, просто для фильтрации
    try:
        is_admin = await is_admin_access(request)
    except HttpError:
        is_admin = False

    # Получаем базовый QuerySet (Lazy) с OLP-фильтрацией на уровне БД
    query_set = await get_client_queryset(user_id=initiator_id, is_admin=is_admin)

    # Применяем фильтры из запроса: строим SQL-запрос, в БД не идем (Lazy)
    # Ninja.FilterSchema применяет фильтры к QuerySet'у, возвращая новый QuerySet
    query_set = filters.filter(query_set)

    return query_set


@router.get("/{client_id}", response={200: ClientOut, **STANDARD_ERRORS})
async def get_client(request: HttpRequest, client_id: UUID) -> Client:
    """
    Получить детальную информацию о клиенте по ID.

    Args:
        request (HttpRequest): Объект входящего запроса.
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

    # Находим клиента, используя селектор для поиска
    client = await get_client_by_id(client_id=client_id, user_id=initiator_id, is_admin=admin_status)

    # Проверяем существование клиента
    if not client:
        log.info(f"Client {client_id} not found (requested by '{initiator_str}')")
        raise HttpError(status_code=404, message="Клиент не найден")

    # Проверка объектных прав (OLP), если бухгалтер запрашивает чужого клиента
    await check_client_access(request=request, client=client)

    # Ninja сам преобразует Client в ClientOut
    return client


@router.post("/", response={201: ClientOut, **STANDARD_ERRORS})
async def create_client_endpoint(request: HttpRequest, payload: ClientCreate) -> tuple[int, Client]:
    """
    Создание нового клиента.
    Доступно только администраторам.

    Args:
        request (HttpRequest): Объект входящего запроса.
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

    # Проверка роли (RBAC)
    await is_admin_access(request)

    # Вызываем сервис создания
    client = await create_client(data=payload, initiator=initiator_id)

    # Возвращаем созданного клиента
    return 201, client


@router.patch("/{client_id}", response={200: ClientOut, **STANDARD_ERRORS})
async def update_client_endpoint(request: HttpRequest, client_id: UUID, payload: ClientUpdate) -> Client:
    """
    Частичное обновление данных клиента.
    Только ответственные лица могут изменять клиента.

    Args:
        request (HttpRequest): Объект входящего запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).
        payload (ClientUpdate): Данные для обновления.

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): Нет прав на редактирование данного клиента.
        HttpError(404): Если клиент не найден.
        HttpError(409): Конфликт данных (например, дубликат УНП).
        HttpError(422): Ошибка структуры передаваемых данных.

    Returns:
        int, Client: Обновленный объект клиента.
    """
    # Получаем инициатора запроса (id для аудита, str для логов)
    initiator_id, initiator_str = await get_request_initiator(request)

    log.info(f"Initiator '{initiator_str}' attempts to update client {client_id}.")

    # Проверяем роли (RBAC)
    admin_status = await is_admin_access(request)

    # Находим клиента, используя селектор для поиска
    client = await get_client_by_id(client_id=client_id, user_id=initiator_id, is_admin=admin_status)

    # Проверяем существование клиента
    if not client:
        raise HttpError(status_code=404, message="Клиент не найден")

    # Проверка объектных прав (OLP)
    await check_client_access(request=request, client=client)

    # Вызываем сервис обновления
    updated_client = await update_client(client=client, data=payload, initiator=initiator_id)

    # Возвращаем обновленного клиента
    return updated_client


@router.delete("/{client_id}", response={204: None, **STANDARD_ERRORS})
async def delete_client_endpoint(request: HttpRequest, client_id: UUID) -> tuple[int, None]:
    """
    Мягкое удаление (Soft Delete) клиента.

    Клиент скрывается из списков, но остается в БД.
    Доступно только администраторам.

    Args:
        request (HttpRequest): Объект входящего запроса.
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

    # Проверяем роли (RBAC)
    admin_status = await is_admin_access(request)

    # Находим клиента, используя селектор для поиска
    client = await get_client_by_id(client_id=client_id, user_id=initiator_id, is_admin=admin_status)

    # Проверяем существование клиента
    if not client:
        raise HttpError(status_code=404, message="Клиент не найден")

    # Вызываем сервис удаления
    await delete_client(client=client, initiator=initiator_id)

    # Возвращаем код ответа
    return 204, None


@router.get("/{client_id}/history", response={200: list[ClientHistoryOut], **STANDARD_ERRORS})
async def get_client_history(request: HttpRequest, client_id: UUID) -> list[dict[str, Any]]:
    """
    Получить журнал аудита (историю изменений) клиента.

    Возвращает список событий с диффами (разницами изменений) и контекстом операции.
    Доступно только администраторам.

    Args:
        request (HttpRequest): Объект входящего запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): При попытке доступа без прав администратора.
        HttpError(404): Если клиент не найден.

    Returns:
        list[dict[str, Any]]: Список событий изменения клиента.
    """
    # Получаем инициатора запроса (id для аудита здесь не нужен, str для логов)
    _, initiator_str = await get_request_initiator(request)

    log.info(f"Initiator '{initiator_str}' requested history for client {client_id}.")

    # Проверка роли (RBAC)
    await is_admin_access(request)

    # Проверяем существование клиента (сам объект не нужен, поэтому .aexists для скорости)
    # TODO: можно искать также по удаленным клиентам через менеджер .all_objects
    client_exists = await Client.objects.filter(id=client_id).aexists()

    if not client_exists:
        raise HttpError(status_code=404, message="Клиент не найден")

    # Получаем данные через селектор
    history_data = await get_client_history_queryset(client_id=client_id)

    # Возвращаем данные (Ninja сам преобразует словари в ClientHistoryOut)
    return history_data
