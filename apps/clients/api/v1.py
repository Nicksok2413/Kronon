"""
API Endpoints для Клиентов (v1).

Предоставляет методы для чтения (GET), создания (POST), обновления (PATCH)
и удаления (DELETE) клиентов.
"""

from typing import Annotated
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
from apps.clients.selectors import get_client_by_id, get_client_queryset
from apps.clients.services import create_client, delete_client, update_client
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
    log.info(f"User {request.user.id} fetching client list.")

    # Получаем базовый QuerySet (Lazy)
    query_set = get_client_queryset()

    # Применяем фильтры: синхронно строим SQL-запрос, в БД не идем (Lazy)
    # Ninja.FilterSchema применяет фильтры к QuerySet'у, возвращая новый QuerySet
    query_set = filters.filter(query_set)

    return query_set


@router.get("/{client_id}", response={200: ClientOut})
async def get_client(request: HttpRequest, client_id: UUID) -> tuple[int, Client]:
    """
    Получить детальную информацию о клиенте по ID.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(404): Если клиент не найден.

    Returns:
        tuple[int, Client]: Код ответа, объект клиента.
    """
    client = await get_client_by_id(client_id=client_id)

    if not client:
        log.info(f"Client {client_id} not found requested by {request.user.id}")
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

    # Получает ID пользователя из запроса
    user_id = request.user.id

    log.info(f"User {user_id} initiates client creation.")

    # Вызываем сервис создания
    client = await create_client(data=payload, user_id=user_id)

    # Возвращаем созданного клиента
    return 201, client


@router.patch("/{client_id}", response={200: ClientOut})
async def update_client_endpoint(request: HttpRequest, client_id: UUID, payload: ClientUpdate) -> tuple[int, Client]:
    """
    Частичное обновление данных клиента.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).
        payload (ClientUpdate): Данные для обновления.

    Raises:
        HttpError(404): Если клиент не найден.

    Returns:
        tuple[int, Client]: Код ответа, обновленный объект клиент.
    """
    # TODO: добавить проверку прав

    # Получает ID пользователя из запроса
    user_id = request.user.id

    log.info(f"User {user_id} initiates update for client {client_id}")

    # Находим клиента, используя селектор для поиска
    client = await get_client_by_id(client_id=client_id)

    # Проверяем существование клиента
    if not client:
        raise HttpError(status_code=404, message="Клиент не найден")

    # Вызываем сервис обновления
    updated_client = await update_client(client=client, data=payload, user_id=user_id)

    # Возвращаем обновленного клиента
    return 200, updated_client


@router.delete("/{client_id}", response={204: None})
async def delete_client_endpoint(request: HttpRequest, client_id: UUID) -> tuple[int, None]:
    """
    Удалить клиента (Soft Delete).

    Args:
        request (HttpRequest): Объект HTTP запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(404): Если клиент не найден.

    Returns:
        tuple[int, None]: Код ответа, None
    """
    # TODO: добавить проверку прав

    # Получает ID пользователя из запроса
    user_id = request.user.id

    log.info(f"User {user_id} initiates deletion of client {client_id}")

    # Находим клиента, используя селектор для поиска
    client = await get_client_by_id(client_id=client_id)

    # Проверяем существование клиента
    if not client:
        raise HttpError(status_code=404, message="Клиент не найден")

    # Вызываем сервис удаления
    await delete_client(client=client, user_id=user_id)

    # Возвращаем код ответа
    return 204, None


@router.get("/{client_id}/history", response={200, list[ClientHistoryOut]})
async def get_client_history(request: HttpRequest, client_id: UUID):
    """
    Получить журнал аудита (историю изменений) клиента.

    Возвращает список снимков состояния объекта, отсортированный от новых к старым.
    Доступно только администраторам.

    Args:
        request (HttpRequest): Объект запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(403): При попытке доступа не эндпойнту без соответствующих прав.

    Returns:
        list[ClientHistoryOut]: Список записей изменений клиента.
    """

    # Проверяем доступ (например, историю видит только Админ)
    if not request.user.is_staff:
        raise HttpError(status_code=403, message="Журнал аудита доступен только администраторам.")

    # Находим клиента, используя селектор для поиска
    client = await get_client_by_id(client_id=client_id)

    # Проверяем существование клиента
    if not client:
        raise HttpError(status_code=404, message="Клиент не найден")

    # Возвращаем историю, отсортированную от новых к старым
    return client.events.order_by("-history_created_at")

    # # Получаем историю (синхронно, так как simple-history пока не полностью async)
    # # Используем select_related для юзера, который сделал изменение
    # # all()[:20] - берем последние 20 изменений
    # history_qs = client.history.select_related("history_user").order_by("-history_date")[:50]
    #
    # # Преобразуем в список асинхронно (для совместимости с async view)
    # return [h async for h in history_qs]
