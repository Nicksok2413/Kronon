"""
Утилиты для работы с инициаторами запросов.
"""

from uuid import UUID

from django.http import HttpRequest


async def get_request_initiator_id(request: HttpRequest) -> UUID | None:
    """
    Вспомогательная функция для безопасного получения ID юзера.

    Args:
        request (HttpRequest): Объект входящего запроса.

    Returns:
        UUID | None: ID пользователя, инициировавшего запрос или None.
    """
    # Если это программный запрос по API-ключу, пользователя в БД нет
    if request.auth == "system_api":
        return None

    # Безопасное асинхронное получение пользователя (распаковывает SimpleLazyObject)
    user = await request.auser()

    return getattr(user, "id", None)
