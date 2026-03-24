"""
Админка журнала аудита.
"""

from typing import Any, cast

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _
from pghistory.admin import EventsAdmin
from rangefilter.filters import DateTimeRangeFilter

from apps.audit.models import KrononEvents


class KrononEventsAdmin(EventsAdmin):
    """
    Расширенная админка аудита изменений (History).
    Работает с ProxyFields и ContextJSONField.
    """

    # Оптимизация поиска (ускоряет `SELECT COUNT(*)` на миллионах строк)
    show_full_result_count = False

    # Немного ускорит админку на больших объёмах
    list_per_page = 50

    search_fields = (
        "pgh_context__user_email",
        "pgh_context__correlation_id",
        "pgh_context__ip_address",
    )

    # Явно запрещаем массовые действия
    actions = None

    # Поля pghistory из settings + кастомные поля
    def get_list_display(self, request: HttpRequest) -> Any:
        """Расширяет отображение полей списка."""
        base_list_display = super().get_list_display(request)  # type: ignore[no-untyped-call]

        return base_list_display + [
            "obj_display",
            "colored_label",
            "service_display",
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
        """Отображает в списке название измененного объекта или email, в случае изменения пользователя."""
        data = obj.pgh_data

        display_value = data.get("name") or data.get("email")

        return str(display_value) if display_value else "-"

    @admin.display(description=_("Сервис"))
    def service_display(self, obj: KrononEvents) -> str:
        """Отображает сервис - источник изменения объекта и детали (задачу или команду)."""
        service = obj.service

        if service == "Admin":
            return "🛠️ Admin"
        if service == "System":
            return "🤖 System"
        if service == "Celery":
            return f"⚙️ {obj.celery_task_name}"
        if service == "CLI":
            return f"💻 CLI: {obj.cli_command[:20]}..."

        return "🌐 API/Web"

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
    def colored_label(self, obj: KrononEvents) -> SafeString:
        """
        Цветовая индикация типов событий.

        Зеленый - Создание нового клиента.
        Оранжевый - Обновление клиента.
        Красный - Удаление клиента (Soft Delete).
        Черный - Удаление клиента (Hard Delete).
        Серый - Неизвестное событие.
        """
        label = obj.pgh_label
        diff = getattr(obj, "pgh_diff", {}) or {}

        # Если это update, проверяем поле deleted_at в диффе
        if label == "update" and "deleted_at" in diff:
            deleted_at_value = diff["deleted_at"][1]  # Кортеж (old, new)

            if deleted_at_value is not None:
                label = "soft_delete"  # Установили дату — удалили
            else:
                label = "restore"  # Сбросили дату в null — восстановили

        # Маппинг цветов
        colors = {
            "insert": "#28a745",  # Зеленый
            "update": "#ffc107",  # Оранжевый
            "soft_delete": "#dc3545",  # Красный
            "restore": "#007bff",  # Синий
            "delete": "#000000",  # Черный (Hard Delete)
        }

        color = colors.get(label, "#6c757d")  # Серый для неизвестных событий

        # Переводим метку для отображения
        labels_map = {
            "insert": "Создание",
            "update": "Обновление",
            "soft_delete": "Мягкое удаление",
            "restore": "Восстановлен",
            "delete": "Физ. удаление",
        }

        display_text = labels_map.get(label, label.upper())

        return format_html('<b style="color:{}; white-space: nowrap;">{}</b>', color, display_text)

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
