"""
Инструменты для интеграции бизнес-логики с аудитом (pghistory).
"""

from collections.abc import Callable
from typing import Any

from asgiref.sync import sync_to_async
from pghistory import context as pghistory_context


async def aexecute_with_audit[T](
    audit_context: dict[str, Any],
    sync_func: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    Выполняет синхронную функцию (ORM запрос) асинхронно, гарантируя
    сохранение контекста pghistory внутри Thread Pool.

    Args:
        audit_context (dict[str, Any]): Словарь с контекстом из request.audit_context.
        sync_func (Callable[..., _T]): Синхронная функция (например, Client.objects.create или client.save).

    Returns:
        _T: Результат выполнения функции.
    """

    def _wrapper() -> T:
        # Выполняем в синхронном потоке, чтобы контекст не потерялся
        with pghistory_context(**audit_context):
            return sync_func(*args, **kwargs)

    return await sync_to_async(_wrapper)()
