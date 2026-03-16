"""
Админка журнала аудита.
"""

from typing import Any, cast

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from pghistory.admin import EventsAdmin
from rangefilter.filters import DateTimeRangeFilter

from apps.audit.models import KrononEvents
from apps.common.admin import KrononBaseAdmin


class KrononEventsAdmin(EventsAdmin, KrononBaseAdmin[Any]):
    """
    Расширенная админка аудита изменений (History).
    Работает с ProxyFields и ContextJSONField.
    """

    search_fields = (
        "pgh_context__user_email",
        "pgh_context__correlation_id",
        "pgh_context__ip_address",
    )

    # Оптимизация поиска (ускоряет `SELECT COUNT(*)` на миллионах строк)
    show_full_result_count = False

    # Явно запрещаем массовые действия
    actions = None

    # Немного ускорит админку на больших объёмах
    list_per_page = 50

    # Поля pghistory из settings + кастомные поля
    def get_list_display(self, request: HttpRequest) -> Any:
        """Расширяет отображение полей списка."""
        base_list_display = super().get_list_display(request)  # type: ignore[no-untyped-call]
        return base_list_display + [
            "obj_display",
            "colored_label",
            "user_email_display",
            "correlation_id_display",
            "ip_address_display",
            "short_diff",
        ]

    # Базовые фильтры pghistory + кастомные фильтры
    def get_list_filter(self, request: HttpRequest) -> Any:
        """Расширяет фильтрацию списка."""
        base_list_filter = super().get_list_filter(request)  # type: ignore[no-untyped-call]
        return base_list_filter + [
            # Фильтрация по дате на уровне БД (UI с календарём)
            ("pgh_created_at", DateTimeRangeFilter),
        ]

    # --- UI helpers ---

    @admin.display(description=_("Объект"))
    def obj_display(self, obj: KrononEvents) -> str:
        """Отображает в списке название или UUID измененного объекта."""
        return str(obj.pgh_data["name"] or obj.pgh_obj_id)

    @admin.display(description=_("Пользователь"))
    def user_email_display(self, obj: KrononEvents) -> str:
        """Отображает в списке Email пользователя (изменившего объект) из контекста запроса."""
        return cast(str, obj.user_email)

    @admin.display(description="Trace ID")
    def correlation_id_display(self, obj: KrononEvents) -> str:
        """Отображает в списке ID (UUID) корреляции из контекста запроса."""
        return cast(str, obj.correlation_id)

    @admin.display(description=_("IP"))
    def ip_address_display(self, obj: KrononEvents) -> str | None:
        """Отображает в списке IP адрес из контекста запроса."""
        return cast(str | None, obj.ip_address)

    @admin.display(description=_("Тип"))
    def colored_label(self, obj: KrononEvents) -> str:
        """
        Цветовая индикация типов событий.

        Зеленый - Создание нового клиента.
        Оранжевый - Обновление клиента.
        Красный - Удаление клиента.
        Черный - По умолчанию.
        """
        colors = {
            "insert": "green",
            "update": "orange",
            "delete": "red",
        }
        color = colors.get(obj.pgh_label, "black")
        return format_html('<b style="color:{}">{}</b>', color, obj.pgh_label)

    @admin.display(description=_("Изменения"))
    def short_diff(self, obj: KrononEvents) -> str:
        """Читаемый короткий diff (без JSON-каши) прямо в list_display."""
        if not getattr(obj, "pgh_diff", None):
            return "—"

        parts: list[str] = []

        for field, (old, new) in obj.pgh_diff.items():
            if field != "updated_at":
                parts.append(f"{field}: {old} → {new}")

        return "; ".join(parts[:3])  # Ограничиваем длину

    # --- Делаем историю неизменяемой (Read-only) ---

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False
