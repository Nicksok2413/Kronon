"""
Вспомогательные утилиты приложения Audit.

Содержит чистые функции для логирования и обертки для выполнения
запросов к БД с сохранением контекста аудита.
"""

from collections.abc import Callable
from typing import Any

from asgiref.sync import sync_to_async
from django.conf import settings
from pghistory import context as pghistory_context


def get_initiator_log_str(audit_context: dict[str, Any]) -> str:
    """
    Формирует строку с информацией об инициаторе запроса для логирования (Loguru).
    Учитывает флаг LOG_DETAILED_AUDIT для скрытия/отображения IP и User-Agent.

    Args:
        audit_context (dict[str, Any]): Словарь контекста аудита, собранный в Middleware.

    Returns:
        str: Форматированная строка (например, "admin@kronon.by [IP: 127.0.0.1, User-Agent: ...]").
    """
    user_email = audit_context.get("user_email") or "Anonymous"

    # Если включена детальная аналитика, добавляем IP адрес и User-Agent
    if settings.LOG_DETAILED_AUDIT:
        ip_address = audit_context.get("ip_address") or "no-ip"
        user_agent = audit_context.get("user_agent") or "no-ua"

        return f"{user_email} [IP: {ip_address}, User-Agent: {user_agent}]"

    # Иначе возвращаем только Email (или 'Anonymous')
    return user_email


async def aexecute_with_audit[T](
    audit_context: dict[str, Any],
    sync_func: Callable[..., T],
    *args: Any,
    **kwargs: Any,
) -> T:
    """
    Выполняет синхронную функцию (обычно ORM запрос) асинхронно, гарантируя
    сохранение контекста pghistory внутри пула потоков (Thread Pool).

    Используется в сервисах (Write Layer) для атомарной записи контекста аудита
    вместе с бизнес-данными.

    Args:
        audit_context (dict[str, Any]): Словарь с контекстом из request.audit_context.
        sync_func (Callable[..., T]): Синхронная функция (например, Client.objects.create или client.save).
        *args (Any): Позиционные аргументы для `sync_func`.
        **kwargs (Any): Именованные аргументы для `sync_func`.

    Returns:
        T: Результат выполнения `sync_func` с сохранением оригинального типа.
    """

    def _wrapper() -> T:
        # Выполняем в синхронном потоке, чтобы контекст (ContextVars) не потерялся
        with pghistory_context(**audit_context):
            return sync_func(*args, **kwargs)

    # Вызываем через sync_to_async, чтобы не блокировать Event Loop
    return await sync_to_async(_wrapper)()
