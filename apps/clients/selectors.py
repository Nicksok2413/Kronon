"""
Селекторы (Read Logic) для приложения Clients.

Отвечают за получение данных из БД.
Используют асинхронный подход для неблокирующего ввода-вывода.
"""

import uuid

from apps.clients.models import Client
from apps.common.managers import SoftDeleteQuerySet


def _get_base_queryset() -> SoftDeleteQuerySet[Client]:
    """
    Внутренний метод для получения базового QuerySet с оптимизацией.
    Подгружает (join) все связанные поля, необходимые для схемы ClientOut.
    """
    return Client.objects.active().select_related(
        "department",
        "accountant",
        "primary_accountant",
        "payroll_accountant",
        "hr_specialist",
    )


async def get_client_list() -> list[Client]:
    """
    Асинхронно получает список всех активных клиентов.

    Использует кастомный метод active() из SoftDeleteManager, чтобы исключить удаленные записи.
    Выполняет запрос к БД и преобразует результат в список.

    Returns:
        list[Client]: Список объектов активных клиентов.
    """
    queryset = _get_base_queryset()

    # Асинхронная итерация по подготовленному QuerySet
    return [client async for client in queryset]


async def get_client_by_id(client_id: uuid.UUID) -> Client | None:
    """
    Асинхронно получает детальную информацию о клиенте по ID.

    Args:
        client_id (uuid.UUID): Уникальный идентификатор клиента (UUIDv7).

    Returns:
        Client | None: Объект клиента, если найден и активен.
                          None, если клиент не найден или удален.
    """
    # .filter().afirst() вместо .aget(), чтобы избежать исключения DoesNotExist и вернуть None
    return await _get_base_queryset().filter(id=client_id).afirst()
