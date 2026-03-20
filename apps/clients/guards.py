"""
Гарды  для приложения Clients.
"""

from uuid import UUID

from django.http import HttpRequest
from loguru import logger as log
from ninja.errors import HttpError

from apps.clients.models import Client
from apps.clients.selectors import get_client_by_id
from apps.common.permissions import check_client_access, is_admin_access


async def get_client_or_404(client_id: UUID, is_deleted: bool = False) -> Client:
    """
    Проверяет существование клиента.

    Args:
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).
        is_deleted (bool): Флаг поиска по мягко удалённым клиентам.

    Raises:
        HttpError(404): Если клиент не найден.

    Returns:
        Client: Объект клиента.
    """
    # Находим клиента, используя селектор для поиска
    client = await get_client_by_id(client_id=client_id, is_deleted=is_deleted)

    # Проверяем существование клиента
    if client:
        log.debug(f"Client found. Name: {client.name}, UNP: {client.unp}")
    else:
        log.warning(f"Client {client_id} not found.")
        raise HttpError(status_code=404, message="Клиент не найден")

    return client


async def get_client_for_admin_or_404(request: HttpRequest, client_id: UUID, is_deleted: bool = False) -> Client:
    """
    Проверяет существование клиента и RBAC-права (система/админ/директор/главбух).

    Args:
        request (HttpRequest): Объект входящего запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).
        is_deleted (bool): Флаг поиска по мягко удалённым клиентам.

    Raises:
        HttpError(404): Если клиент не найден.
        HttpError(403): Если нет прав доступа.

    Returns:
        Client: Объект клиента.
    """
    client = await get_client_or_404(client_id=client_id, is_deleted=is_deleted)

    # Проверка прав (RBAC)
    await is_admin_access(request)

    return client


async def get_client_for_edit_or_404(request: HttpRequest, client_id: UUID) -> Client:
    """
    Проверяет существование клиента и права (RBAC + OLP).

    Args:
        request (HttpRequest): Объект входящего запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(404): Если клиент не найден.
        HttpError(403): Если нет прав доступа.

    Returns:
        Client: Объект клиента.
    """
    client = await get_client_or_404(client_id)

    # Проверка прав (RBAC + OLP)
    await check_client_access(request=request, client=client)

    return client
