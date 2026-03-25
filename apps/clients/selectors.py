"""
Селекторы (Read Logic) для приложения Clients.

Отвечают за получение данных из БД.
Используют асинхронный подход для неблокирующего ввода-вывода.
"""

from uuid import UUID

from loguru import logger as log

from apps.clients.models import Client
from apps.common.managers import SoftDeleteQuerySet


def _get_base_client_queryset(is_deleted: bool = False) -> SoftDeleteQuerySet[Client]:
    """
    Технический метод для оптимизации и сортировки базового QuerySet для списка клиентов.

    Если передан флаг is_deleted=True, формирует QuerySet по мягко удалённым клиентам.
    Применяет `select_related` для всех связанных полей, необходимых в API,
    чтобы избежать проблемы N+1 запросов.
    Гарантирует сортировку по ID (в обратном порядке).

    Args:
        is_deleted (bool): Флаг формирования QuerySet по мягко удалённым клиентам.

    Returns:
        SoftDeleteQuerySet[Client]: Оптимизированный базовый QuerySet.
    """
    # Логируем на уровне DEBUG, так как это частая операция
    log.debug("Building base client queryset with select_related")

    # Если is_deleted=True, формируем по мягко удалённым клиентам, иначе по активным
    search_clients = Client.objects.deleted() if is_deleted else Client.objects.active()

    return (
        search_clients.select_related(
            "department",
            "accountant",
            "primary_accountant",
            "payroll_accountant",
            "hr_specialist",
        ).order_by("-id")  # Оптимизация N+1  # Гарантируем сортировку
    )


def get_client_queryset(user_id: UUID, is_admin: bool) -> SoftDeleteQuerySet[Client]:
    """
    Возвращает оптимизированный QuerySet для списка клиентов с учетом прав доступа (OLP).

    Применяет OLP-фильтрацию по пользователю.

    Args:
        user_id (UUID): ID инициатора запроса для OLP-фильтрации.
        is_admin (bool): Флаг наличия административных прав.

    Returns:
        SoftDeleteQuerySet[Client]: Оптимизированный QuerySet с OLP-фильтрацией.
    """
    return _get_base_client_queryset().for_user(user_id, is_admin)  # OLP-фильтрация


async def get_client_by_id(client_id: UUID, is_deleted: bool = False) -> Client | None:
    """
    Асинхронно получает детальную информацию о клиенте по ID.

    Использует оптимизированный базовый QuerySet (без OLP-фильтрации).

    Args:
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).
        is_deleted (bool): Флаг поиска по мягко удалённым клиентам.

    Returns:
        Client | None: Объект клиента или None, если не найден/удален.
    """
    try:
        # Оптимизированный базовый QuerySet
        queryset = _get_base_client_queryset(is_deleted)

        # .afirst() вместо .aget(), чтобы избежать исключения DoesNotExist и вернуть None
        return await queryset.filter(id=client_id).afirst()

    except Exception as exc:
        log.error(f"DB Error while fetching client. ID: {client_id}: {exc}")
        # Глобальный хендлер превратит это в 500
        raise
