"""
Утилиты для интеграции системы аудита (pghistory) с асинхронным кодом.
"""

from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from pghistory import context as pghistory_context


async def aexecute_with_audit[T](
    initiator: UUID | str | None,
    async_func: Callable[..., Awaitable[T]],
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    Выполняет асинхронную функцию (ORM запрос), предварительно обернув её
    в контекст аудита pghistory.

    Сохраняет 100% нативную асинхронность (без использования Thread Pool),
    максимально утилизируя возможности Psycopg 3.

    Args:
        initiator (UUID | str | None): ID инициатора запроса.
        async_func (Callable[..., Awaitable[T]]): Асинхронная функция (например, `client.asave`).
        *args: Позиционные аргументы для `async_func`.
        **kwargs: Именованные аргументы для `async_func`.

    Returns:
        T: Результат выполнения `async_func` с сохранением оригинального типа.
    """
    # Приводим initiator к строке, чтобы pghistory корректно сериализовал его в JSON
    initiator_str = str(initiator) if initiator else None

    # Оборачиваем в контекст pghistory для записи ID инициатора запроса
    # pghistory работает через ContextVars, которые нативно поддерживаются в asyncio
    # Это операция в памяти Python (установка переменной контекста)
    # Она не делает запросов в БД в момент входа (__enter__), а просто говорит:
    # "Следующий запрос в БД должен быть помечен этим юзером"

    # Контекст устанавливается для текущей асинхронной задачи
    with pghistory_context(user=initiator_str):
        return await async_func(*args, **kwargs)
