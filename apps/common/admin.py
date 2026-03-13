"""
Админка журнала аудита.
"""

from typing import Any

from django.http import HttpRequest
from pghistory.admin import EventsAdmin
from rangefilter.filters import DateTimeRangeFilter


class KrononEventsAdmin(EventsAdmin):
    """
    Расширенная админка аудита изменений (History).
    Работает с ProxyFields и ContextJSONField.
    """

    search_fields = (
        "pgh_context__user_email",
        "pgh_context__correlation_id",
        "pgh_context__ip_address",
    )

    # Вместо prefetch_related используем оптимизацию поиска
    show_full_result_count = False  # Ускоряет SELECT COUNT(*) на миллионах строк

    # Явно запрещаем массовые действия
    actions = None

    # Немного ускорит админку на больших объёмах
    list_per_page = 50

    # Базовые фильтры pghistory + кастомные фильтры
    def get_list_filter(self, request):
        return super().get_list_filter(request) + [
            # Фильтрация по дате на уровне БД (UI с календарём)
            ("pgh_created_at", DateTimeRangeFilter),
        ]

    # @admin.display(description="User/Email")
    # def user_display(self, obj):
    #     return obj.pgh_context.get("user_email") or obj.pgh_context.user
    #
    # @admin.display(description="Trace ID")
    # def correlation_id_display(self, obj):
    #     return obj.pgh_context.get("correlation_id")
    #
    # @admin.display(description=_("IP"))
    # def ip_display(self, obj):
    #     return obj.pgh_context.get("ip_address")
    #
    # @admin.display(description=_("Method"))
    # def method_display(self, obj):
    #     return obj.pgh_context.get("method")

    # --- Делаем историю неизменяемой (Read-only) ---

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False
