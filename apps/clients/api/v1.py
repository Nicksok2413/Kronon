"""
API Endpoints для Клиентов (v1).

Предоставляет методы для чтения и управления клиентами.
Весь ввод-вывод выполняется асинхронно.
"""

import uuid

from django.http import HttpRequest
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import JWTAuth

from apps.clients.models import Client
from apps.clients.schemas.client import ClientOut
from apps.clients.selectors import get_client_by_id, get_client_list

# Создаем роутер
# auth=JWTAuth() - все эндпоинты в этом роутере требуют токен
router = Router(auth=JWTAuth())


@router.get("/", response=list[ClientOut])
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


@router.get("/{client_id}", response=ClientOut)
async def get_client(request: HttpRequest, client_id: uuid.UUID) -> Client:
    """
    Получить детальную информацию о клиенте по ID.

    Если клиент не найден или был удален (Soft Delete), возвращается 404.

    Args:
        request (HttpRequest): Объект HTTP запроса.
        client_id (uuid.UUID): Уникальный идентификатор клиента (UUIDv7).

    Returns:
        Client: Объект клиента.

    Raises:
        HttpError(404): Если клиент не найден.
    """
    client = await get_client_by_id(client_id)

    if not client:
        raise HttpError(status_code=404, message="Клиент не найден")

    # Ninja сам преобразует Client в ClientOut
    return client
