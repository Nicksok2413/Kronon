"""
Селекторы (Read Logic) для приложения Clients.

Отвечают за получение данных из БД.
Используют асинхронный подход для неблокирующего ввода-вывода.
"""

import uuid

from apps.clients.models import Client


async def get_client_list() -> list[Client]:
    """
    Асинхронно получает список всех активных клиентов.

    Использует кастомный метод active() из SoftDeleteManager, чтобы исключить удаленные записи.
    Выполняет запрос к БД и преобразует результат в список.

    Returns:
        list[Client]: Список объектов активных клиентов.
    """
    # В Django ORM QuerySet ленивый
    # Чтобы выполнить запрос асинхронно, итерируемся по нему через `async for`
    # Это позволяет Event Loop'у переключаться на другие задачи во время I/O
    queryset = Client.objects.active()
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
    # .filter().afirst() вместо .get(), чтобы избежать исключения DoesNotExist и вернуть None
    # afirst() - нативный асинхронный метод Django ORM
    return await Client.objects.active().filter(id=client_id).afirst()
