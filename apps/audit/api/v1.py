"""
API Endpoints для Аудита (v1).

Предоставляет (GET) историю изменения объектов (клиентов и т.д.).
"""

from typing import Any
from uuid import UUID

from django.http import HttpRequest
from loguru import logger as log
from ninja import Router
from ninja.errors import HttpError
from ninja_jwt.authentication import AsyncJWTAuth

from apps.audit.schemas import ClientHistoryOut
from apps.audit.selectors import get_client_history_queryset
from apps.audit.utils import get_initiator_log_str
from apps.clients.models import Client
from apps.common.auth import AsyncApiKeyAuth
from apps.common.permissions import is_admin_access
from apps.common.schemas import STANDARD_ERRORS

# Эндпоинты доступны как по JWT, так и по API Ключу (для скриптов)
router = Router(auth=[AsyncJWTAuth(), AsyncApiKeyAuth()])


@router.get("/clients/{client_id}", response={200: list[ClientHistoryOut], **STANDARD_ERRORS})
async def get_client_history(request: HttpRequest, client_id: UUID) -> list[dict[str, Any]]:
    """
    Получить журнал аудита (историю изменений) клиента.

    Возвращает список событий с диффами (разницами изменений) и контекстом операции.
    Доступно только системе и администраторам.

    Args:
        request (HttpRequest): Объект входящего HTTP запроса.
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Raises:
        HttpError(401): Токен отсутствует или недействителен.
        HttpError(403): При попытке доступа без прав администратора.
        HttpError(404): Если клиент не найден.

    Returns:
        list[dict[str, Any]]: Список событий изменения клиента.
    """
    # Достаем контекст аудита, собранный в Middleware
    audit_context = getattr(request, "audit_context", {})

    # Логируем инициатора запроса
    initiator_str = get_initiator_log_str(audit_context)
    log.info(f"Initiator '{initiator_str}' requested history for client {client_id}.")

    # Проверяем права (RBAC)
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
