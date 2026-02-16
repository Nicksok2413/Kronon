"""
API Endpoints для Клиентов (v1).

Предоставляет методы для чтения и управления клиентами.
Весь ввод-вывод выполняется асинхронно.
"""

import uuid

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import AsyncJWTAuth

from apps.clients.models import Client
from apps.clients.schemas.client import ClientCreate, ClientOut, ClientUpdate
from apps.clients.selectors import get_client_by_id, get_client_list
from apps.clients.services import create_client, update_client

# auth=AsyncJWTAuth() - все эндпоинты в этом роутере требуют токен
router = Router(auth=AsyncJWTAuth())


@router.get("/", response={200: list[ClientOut]})
async def list_clients(request: HttpRequest) -> list[Client]:
    """
    Получить список всех активных клиентов.

    Возвращает только тех клиентов, у которых не установлено поле `deleted_at`.

    Args:
        request (HttpRequest): Объект HTTP запроса.

    Returns:
        list[Client]: Список объектов активных клиентов.
    """
    # Ninja сам преобразует list[Client] в list[ClientOut]
    return await get_client_list()


@router.get("/{client_id}", response={200: ClientOut})
async def get_client(request: HttpRequest, client_id: uuid.UUID) -> Client:
    """
    Получить детальную информацию о клиенте по ID.

    Если клиент не найден или был удален (Soft Delete), возвращается 404.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        client_id (uuid.UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(404): Если клиент не найден.

    Returns:
        Client: Объект клиента.
    """
    client = await get_client_by_id(client_id=client_id)

    if not client:
        raise HttpError(status_code=404, message="Клиент не найден")

    # Ninja сам преобразует Client в ClientOut
    return client


@router.post("/", response={201: ClientOut})
async def create_client_endpoint(request: HttpRequest, payload: ClientCreate) -> tuple[int, Client]:
    """
    Создание нового клиента.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        payload (ClientCreate): Данные для создания.

    Returns:
        Client: Созданный объект клиента.
    """
    # TODO: добавить проверку прав (например, только админ или lead_acc)
    # if not request.user.ahas_perm("clients.add_client"): ...

    client = await create_client(data=payload)
    return 201, client


@router.patch("/{client_id}", response={200: ClientOut})
async def update_client_endpoint(request: HttpRequest, client_id: uuid.UUID, payload: ClientUpdate) -> Client:
    """
    Частичное обновление данных клиента.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        client_id (uuid.UUID): Уникальный идентификатор клиента (UUIDv7).
        payload (ClientUpdate): Данные для обновления.

    Raises:
        HttpError(404): Если клиент не найден.

    Returns:
        Client: Обновленный объект клиент.
    """
    # Сначала находим клиента, используя селектор для поиска
    client = await get_client_by_id(client_id=client_id)

    if not client:
        raise HttpError(404, "Клиент не найден")

    # TODO: добавить проверку прав

    # Вызываем сервис обновления
    updated_client = await update_client(client=client, data=payload)

    return updated_client
