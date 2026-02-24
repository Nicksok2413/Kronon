"""
Селекторы (Read Logic) для приложения Clients.

Отвечают за получение данных из БД.
Используют асинхронный подход для неблокирующего ввода-вывода.
"""

from uuid import UUID

from loguru import logger as log

from apps.clients.models import Client
from apps.common.managers import SoftDeleteQuerySet


def get_client_queryset() -> SoftDeleteQuerySet[Client]:
    """
    Возвращает базовый QuerySet для списка клиентов с оптимизацией.

    Применяет `select_related` для всех связанных полей, необходимых в API,
    чтобы избежать проблемы N+1 запросов.
    Гарантирует сортировку по ID (в обратном порядке).

    Returns:
        SoftDeleteQuerySet[Client]: Оптимизированный QuerySet.
    """
    # Логируем на уровне DEBUG, так как это частая операция
    log.debug("Building base client queryset with select_related")

    return (
        Client.objects.active()
        .select_related(
            "department",
            "accountant",
            "primary_accountant",
            "payroll_accountant",
            "hr_specialist",
        )
        .order_by("-id")
    )  # Гарантируем сортировку


async def get_client_by_id(client_id: UUID) -> Client | None:
    """
    Асинхронно получает детальную информацию о клиенте по ID.

    Использует оптимизированный QuerySet.

    Args:
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).

    Returns:
        Client | None: Объект клиента или None, если не найден/удален.
    """
    log.debug(f"Fetching client. ID: {client_id}")

    try:
        # .afirst() вместо .aget(), чтобы избежать исключения DoesNotExist и вернуть None
        client = await get_client_queryset().filter(id=client_id).afirst()

        if client:
            log.debug(f"Client found: name: {client.name}, UNP: {client.unp}")
        else:
            log.warning(f"Client not found or deleted. ID: {client_id}")

        return client

    except Exception as exc:
        log.error(f"DB Error while fetching client. ID: {client_id}: {exc}")
        # Глобальный хендлер превратит это в 500
        raise
