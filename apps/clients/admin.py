"""
Админка для клиентов и журнала аудита.
"""

from typing import Any

from django.contrib import admin
from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from pghistory.admin import EventModelAdmin
from rangefilter.filters import DateTimeRangeFilter

from apps.clients.models import Client, ClientEvent


@admin.register(ClientEvent)
class ClientEventAdmin(EventModelAdmin):
    """
    Админка для просмотра аудита изменений (History).
    Наследуется от EventModelAdmin для корректного отображения Diff.
    """

    def get_queryset(self, request: HttpRequest) -> QuerySet[ClientEvent]:
        """
        Переопределяем метод получения queryset.
        Django по умолчанию тянет тяжелый pgh_data.
        Откладываем (.defer) загрузку pgh_data, так как не используем его в list_display.
        Это дает буст к производительности.
        """
        queryset = super().get_queryset(request)
        return queryset.defer("pgh_data")

    ordering = ("-pgh_created_at",)

    # Отображаем стандартные поля pghistory + прокси поля
    list_display = [
        "pgh_created_at",
        "pgh_label",
        "client_info",
        "short_diff",  # Читаемый короткий Diff
        "get_user_info",  # Используем проксированный FK
        "app_source",
        "ip_address",
    ]

    list_filter = [
        "pgh_label",
        "app_source",
        ("pgh_created_at", DateTimeRangeFilter),  # Фильтрация по дате (UI с календарём) на уровне БД
    ]

    # Делаем JOIN таблицы пользователей, чтобы не было N+1 запросов при отрисовке списка
    list_select_related = ("pgh_context__user",)

    # Поиск по имени/унп клиента, email автора изменений и по IP адресу
    search_fields = (
        "pgh_obj__name",
        "pgh_obj__unp",
        "user__email",  # Поиск через FK работает нативно
        "user_email",  # Поиск по JSON на случай удаленного юзера
        "ip_address",
    )

    # Явно запрещаем массовые действия
    actions = None

    # Немного ускорит админку на больших объёмах
    list_per_page = 50

    @admin.display(description=_("Изменения"))
    def short_diff(self, obj: ClientEvent) -> str:
        """Читаемый короткий diff (без JSON-каши) прямо в list_display."""
        if not obj.pgh_diff:
            return "—"

        parts = []

        for field, (old, new) in obj.pgh_diff.items():
            parts.append(f"{field}: {old} → {new}")

        return "; ".join(parts[:3])  # Ограничиваем длину

    @admin.display(description=_("Клиент (Snapshot)"))
    def client_info(self, obj: ClientEvent) -> str:
        """Отображает информацию об клиенте на момент события."""
        return f"{obj.name} ({obj.unp})"

    @admin.display(description=_("Автор изменения"), ordering="user__email")
    def get_user_info(self, obj: ClientEvent) -> str:
        """Показывает ФИО и Email автора изменения клиента (или Email из контекста, если удален)."""
        # Если юзер есть в БД - берем его актуальные данные
        if obj.user_id and obj.user:
            return f"{obj.user.full_name_rus} ({obj.user.email})"

        # Если юзера удалили, берем email из JSON-слепка истории
        if obj.user_email:
            return f"Удален ({obj.user_email})"

        return "System / Unknown"

    @admin.display(description=_("Тип"))
    def colored_label(self, obj: ClientEvent) -> str:
        """
        Цвета для типов событий.

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

    # --- Делаем историю неизменяемой (Read-only) ---
    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False


class ClientEventInline(admin.TabularInline[ClientEvent, Client]):
    """
    Инлайн для отображения истории в карточке клиента.
    """

    model = ClientEvent
    extra = 0
    can_delete = False
    readonly_fields = (
        "pgh_created_at",
        "pgh_label",
        "user",
        "app_source",
    )
    verbose_name_plural = _("События")
    ordering = ("-pgh_created_at",)

    def has_add_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin[Client]):
    """Управление клиентами."""

    list_display = (
        "name",
        "unp",
        "org_type",
        "tax_system",
        "status",
        "department",
        "accountant",
        "primary_accountant",
        "payroll_accountant",
        "hr_specialist",
    )

    list_filter = (
        "status",
        "department",
        "org_type",
        "tax_system",
        "accountant",
        "primary_accountant",
        "payroll_accountant",
        "hr_specialist",
    )

    search_fields = ("name", "full_legal_name", "unp")

    # Оптимизация запросов (чтобы не делать N+1 запрос для каждого юзера в списке)
    list_select_related = (
        "department",
        "accountant",
        "primary_accountant",
        "payroll_accountant",
        "hr_specialist",
    )

    # Группировка полей
    fieldsets = (
        (
            _("Основное"),
            {
                "fields": (
                    "status",
                    "name",
                    "full_legal_name",
                    "unp",
                    "org_type",
                    "department",
                )
            },
        ),
        (
            _("Команда и Учет"),
            {"fields": ("tax_system", "accountant", "primary_accountant", "payroll_accountant", "hr_specialist")},
        ),
        (_("Контакты и Интеграции"), {"fields": ("contact_info", "google_folder_id")}),
    )

    # Автокомплит (поиск в выпадающем списке), чтобы список не тормозил, если юзеров станет много
    autocomplete_fields = (
        "accountant",
        "primary_accountant",
        "payroll_accountant",
        "hr_specialist",
    )

    # Добавляем историю изменения клиента
    inlines = (ClientEventInline,)
