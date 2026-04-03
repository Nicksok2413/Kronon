"""
Селекторы (Read Logic) для приложения Clients.

Отвечают за получение данных из БД.
Используют асинхронный подход для неблокирующего ввода-вывода.
Инкапсулируют логику JOIN-ов (select_related) и OLP фильтрации.
"""

from typing import Literal
from uuid import UUID

from loguru import logger as log

from apps.clients.models import Client
from apps.common.managers import SoftDeleteQuerySet


def _get_base_client_queryset(status: Literal["active", "deleted", "all"] = "active") -> SoftDeleteQuerySet[Client]:
    """
    Технический метод для оптимизации и сортировки базового "ленивого" (Lazy) QuerySet для списка клиентов.

    Применяет `select_related` для всех связанных полей, необходимых в API, чтобы избежать проблемы N+1 запросов.
    Гарантирует сортировку по ID (в обратном порядке).

    Args:
        status (Literal): Статус записей ("active" - активные, "deleted" - удаленные/неактивные, "all" - все).

    Returns:
        SoftDeleteQuerySet[Client]: Ленивый (Lazy) базовый QuerySet.
    """
    # Логируем на уровне DEBUG, так как это частая операция
    log.debug(f"Building base client queryset (status={status}) with select_related")

    # Формируем QuerySet в зависимости от значения status
    if status == "deleted":
        search_clients = Client.objects.deleted()
    elif status == "all":
        search_clients = Client.objects.all()
    else:
        search_clients = Client.objects.active()

    return search_clients.select_related(
        "department",
        # Подгружаем связи для accountant
        "accountant__department",
        "accountant__profile",
        # Подгружаем связи для primary_accountant
        "primary_accountant__department",
        "primary_accountant__profile",
        # Подгружаем связи для payroll_accountant
        "payroll_accountant__department",
        "payroll_accountant__profile",
        # Подгружаем связи для hr_specialist
        "hr_specialist__department",
        "hr_specialist__profile",
    ).order_by("-id")


def get_client_queryset(
    user_id: UUID,
    is_admin: bool,
    status: Literal["active", "deleted", "all"] = "active",
) -> SoftDeleteQuerySet[Client]:
    """
    Возвращает оптимизированный QuerySet для списка клиентов с учетом прав доступа (OLP).

    Возвращает "ленивый" (Lazy) QuerySet. Его можно передавать в @paginate декоратор Ninja,
    который сам наложит LIMIT/OFFSET и асинхронно выполнит запрос к БД.
    Применяет OLP-фильтрацию по пользователю.

    Args:
        user_id (UUID): ID инициатора запроса для OLP-фильтрации.
        is_admin (bool): Флаг наличия административных прав.
        status (Literal): Статус записей ("active" - активные, "deleted" - удаленные/неактивные, "all" - все).

    Returns:
        SoftDeleteQuerySet[Client]: Ленивый (Lazy) QuerySet с OLP-фильтрацией.
    """
    return _get_base_client_queryset(status=status).for_user(user_id=user_id, is_admin=is_admin)  # OLP-фильтрация


async def get_client_by_id(client_id: UUID, status: Literal["active", "deleted", "all"] = "active") -> Client | None:
    """
    Асинхронно получает детальную информацию о клиенте по ID.

    Использует оптимизированный базовый QuerySet (без OLP-фильтрации).

    Args:
        client_id (UUID): Уникальный идентификатор клиента (UUIDv7).
        status (Literal): Статус записей ("active" - активные, "deleted" - удаленные/неактивные, "all" - все).

    Returns:
        Client | None: Объект клиента или None, если не найден.
    """
    try:
        # Оптимизированный базовый QuerySet
        queryset = _get_base_client_queryset(status=status)

        # .afirst() вместо .aget(), чтобы избежать исключения DoesNotExist и вернуть None
        return await queryset.filter(id=client_id).afirst()

    except Exception as exc:
        log.error(f"DB Error while fetching client. ID: {client_id}: {exc}")
        # Глобальный хендлер превратит это в 500
        raise
