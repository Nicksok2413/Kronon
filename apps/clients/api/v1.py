"""
API Endpoints для Клиентов (v1).

Предоставляет методы для чтения (GET), создания (POST), обновления (PATCH)
и удаления (DELETE) клиентов.
"""

import uuid
from typing import TYPE_CHECKING, Annotated

from django.http import HttpRequest
from loguru import logger as log
from ninja import Query, Router
from ninja.errors import HttpError
from ninja.pagination import PageNumberPagination, paginate
from ninja_jwt.authentication import AsyncJWTAuth

from apps.clients.models import Client
from apps.clients.schemas import ClientCreate, ClientFilter, ClientOut, ClientUpdate
from apps.clients.selectors import get_client_by_id, get_client_queryset
from apps.clients.services import create_client, delete_client, update_client

if TYPE_CHECKING:
    from apps.common.managers import SoftDeleteQuerySet

# auth=AsyncJWTAuth() - все эндпоинты в этом роутере требуют авторизацию (JWT-токен)
router = Router(auth=AsyncJWTAuth())


@router.get("/", response={200: list[ClientOut]})
@paginate(PageNumberPagination, page_size=20)
async def list_clients(
    request: HttpRequest,
    filters: Annotated[ClientFilter, Query(...)],
) -> SoftDeleteQuerySet[Client]:
    """
    Получить список клиентов с фильтрацией и пагинацией.

    Args:
        request (HttpRequest): Объект запроса.
        filters (ClientFilter): Параметры фильтрации из Query Params.

    Returns:
        SoftDeleteQuerySet[Client]: Отфильтрованный список клиентов (пагинация применяется декоратором).
    """
    try:
        log.info(f"User {request.user.id} requested client list. Filters: {filters.dict(exclude_none=True)}")

        # Получаем базовый QuerySet (ленивый)
        query_set = get_client_queryset()

        # Применяем фильтры (синхронно строим SQL-запрос, в БД не идем)
        query_set = filters.filter(query_set)

        return query_set

    except Exception as exc:
        log.error(f"Error fetching client list: {exc}")
        # Глобальный хендлер превратит это в 500
        raise


@router.get("/{client_id}", response={200: ClientOut})
async def get_client(request: HttpRequest, client_id: uuid.UUID) -> tuple[int, Client]:
    """
    Получить детальную информацию о клиенте по ID.

    Если клиент не найден или был удален (Soft Delete), возвращается 404.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        client_id (uuid.UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(404): Если клиент не найден.

    Returns:
        tuple[int, Client]: Код ответа, объект клиента.
    """
    client = await get_client_by_id(client_id=client_id)

    if not client:
        log.info(f"Client {client_id} not found for user {request.user.id}")
        raise HttpError(status_code=404, message="Клиент не найден")

    # Ninja сам преобразует Client в ClientOut
    return 200, client


@router.post("/", response={201: ClientOut})
async def create_client_endpoint(request: HttpRequest, payload: ClientCreate) -> tuple[int, Client]:
    """
    Создание нового клиента.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        payload (ClientCreate): Данные для создания.

    Returns:
        tuple[int, Client]: Код ответа, созданный объект клиента.
    """
    # TODO: добавить проверку прав (например, только админ или lead_acc)
    # if not request.user.ahas_perm("clients.add_client"): ...

    log.info(f"User {request.user.id} creates client. UNP: {payload.unp}, name: {payload.name}")

    try:
        # Сервис возвращает "чистый" объект клиента (ID и базовые поля)
        client = await create_client(data=payload)

        # API должен вернуть схему ClientOut с полными данными связей (department, accountant и т.д.)
        # Делаем рефреш через селектор с подгрузкой связей
        full_client = await get_client_by_id(client_id=client.id)

        # Теоретически невозможно, что его нет, но для Mypy:
        if not full_client:
            log.critical(f"Client not found after creation! ID: {client.id}")
            raise RuntimeError(f"Client not found after creation. ID: {client.id}")

        # Возвращаем созданного клиента с полными данными
        return 201, full_client

    except Exception as exc:
        log.error(f"Unexpected error in create_client_endpoint: {exc}")
        # Глобальный хендлер превратит это в 500
        raise


@router.patch("/{client_id}", response={200: ClientOut})
async def update_client_endpoint(
    request: HttpRequest, client_id: uuid.UUID, payload: ClientUpdate
) -> tuple[int, Client]:
    """
    Частичное обновление данных клиента.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        client_id (uuid.UUID): Уникальный идентификатор клиента (UUIDv7).
        payload (ClientUpdate): Данные для обновления.

    Raises:
        HttpError(404): Если клиент не найден.

    Returns:
        tuple[int, Client]: Код ответа, обновленный объект клиент.
    """
    # TODO: добавить проверку прав

    log.info(f"User {request.user.id} updates client {client_id}.")

    # Находим клиента, используя селектор для поиска
    client = await get_client_by_id(client_id=client_id)

    if not client:
        raise HttpError(status_code=404, message="Клиент не найден")

    try:
        # Сервис возвращает полный объект клиента с подгрузкой связей
        updated_client = await update_client(client=client, data=payload)
        # Возвращаем обновленного клиента с полными данными
        return 200, updated_client

    except Exception as exc:
        log.error(f"Error in update_client_endpoint: {exc}")
        # Глобальный хендлер превратит это в 500
        raise


@router.delete("/{client_id}", response={204: None})
async def delete_client_endpoint(request: HttpRequest, client_id: uuid.UUID) -> None:
    """
    Удалить клиента (Soft Delete).

    Args:
        request (HttpRequest): Объект HTTP запроса.
        client_id (uuid.UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(404): Если клиент не найден.
    """
    # TODO: добавить проверку прав

    log.info(f"User {request.user.id} requests deletion of client {client_id}")

    # Находим клиента, используя селектор для поиска
    client = await get_client_by_id(client_id)

    if not client:
        raise HttpError(status_code=404, message="Клиент не найден")

    try:
        await delete_client(client)

    except Exception as exc:
        log.error(f"Error deleting client {client_id}: {exc}")
        # Глобальный хендлер превратит это в 500
        raise

    return None
