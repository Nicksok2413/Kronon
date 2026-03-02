"""
Permissions system for Ninja API endpoints.

RBAC (Role-Based Access Control) и OLP (Object-Level Permissions)
"""

from django.http import HttpRequest
from ninja.errors import HttpError

from apps.clients.models import Client
from apps.users.models import UserRole


def require_admin(request: HttpRequest) -> None:
    """
    Разрешает доступ только Директору или Staff.

    Args:
        request (HttpRequest): Объект входящего запроса.

    Raises:
        HttpError(403): Если прав нет.
    """
    user = request.user

    if not user.is_staff and user.role != UserRole.DIRECTOR:
        raise HttpError(status_code=403, message="Доступ запрещен: требуются права администратора.")


async def check_client_access(request: HttpRequest, client: Client) -> None:
    """
    Проверяет, имеет ли текущий пользователь право управлять данным клиентом.

    Логика:
    1. Администраторы и Директора могут редактировать/удалять всё.
    2. Главный бухгалтер может редактировать всё.
    3. Линейный бухгалтер может редактировать только тех клиентов,
       где он указан как ответственный (accountant, primary, payroll, hr).

    Args:
        request (HttpRequest): Объект входящего запроса.
        client (Client): Экземпляр клиента из БД.

    Raises:
        HttpError(403): Если прав нет.
    """
    user = request.user

    # Суперпользователи, директора и главбухи имеют полный доступ к клиентам
    if user.is_staff or user.role in (UserRole.DIRECTOR, UserRole.CHIEF_ACCOUNTANT):
        return None

    # Проверяем объектные права (связи)
    # Если юзер - кто-то из ответственных за этого клиента, пускаем
    allowed_users = [
        client.accountant_id,
        client.primary_accountant_id,
        client.payroll_accountant_id,
        client.hr_specialist_id,
    ]

    if user.id in allowed_users:
        return None

    # Иначе - отказ
    raise HttpError(
        status_code=403,
        message=f"У вас нет прав на редактирование клиента {client.name}. Вы не назначены ответственным сотрудником.",
    )


# def has_api_key(request: HttpRequest) -> None:
#     """
#     Проверяет внутренний API-ключ (для межсервисного взаимодействия).
#
#     Args:
#         request (HttpRequest): Объект HTTP запроса.
#     """
#     api_key = request.headers.get("X-API-Key")
#
#     # settings.INTERNAL_API_KEY
#     if api_key != "secret-key":
#         raise HttpError(403, "Неверный API-ключ.")
