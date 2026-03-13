"""
Админка для клиентов и журнала аудита.
"""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from pghistory.admin import EventModelAdmin
from rangefilter.filters import DateTimeRangeFilter

from apps.clients.models import Client, ClientEventProxy

# ---------------------------------------------------------
# Client history admin
# ---------------------------------------------------------


@admin.register(ClientEventProxy)
class ClientEventAdmin(EventModelAdmin):
    """
    Админка для просмотра аудита изменений (History).
    Работает с ProxyFields и ContextJSONField.
    """

    date_hierarchy = "pgh_created_at"

    list_display = [
        "pgh_created_at",
        "get_client",
        "colored_label",
        "short_diff",
        "get_user_email",
        "get_app_source",
        "get_ip_address",
        "get_user_agent",
        "get_url",
        "get_method",
        "get_celery_task",
        "get_command",
    ]

    list_filter = [
        "pgh_label",
        ("pgh_created_at", DateTimeRangeFilter),  # Фильтрация по дате (UI с календарём) на уровне БД
    ]

    # Поиск по имени/унп клиента, email автора изменений и по IP адресу
    search_fields = ("pgh_context",)

    readonly_fields = (
        "pgh_created_at",
        "pgh_label",
        "pgh_context",
    )

    # Явно запрещаем массовые действия
    actions = None

    # Немного ускорит админку на больших объёмах
    list_per_page = 10

    # --- UI helpers ---

    @admin.display(description="Клиент")
    def get_client(self, obj: ClientEventProxy) -> Any:
        return obj.pgh_obj

    @admin.display(description="ID пользователя")
    def get_user_id(self, obj: ClientEventProxy) -> Any | None:
        return (obj.pgh_context or {}).get("user")

    @admin.display(description="Email пользователя")
    def get_user_email(self, obj: ClientEventProxy) -> Any | None:
        return (obj.pgh_context or {}).get("user_email")

    @admin.display(description=_("Источник"))
    def get_app_source(self, obj: ClientEventProxy) -> Any | None:
        return (obj.pgh_context or {}).get("app_source")

    @admin.display(description=_("IP адрес"))
    def get_ip_address(self, obj: ClientEventProxy) -> Any | None:
        return (obj.pgh_context or {}).get("ip_address")

    @admin.display(description=_("User-Agent"))
    def get_user_agent(self, obj: ClientEventProxy) -> Any | None:
        return (obj.pgh_context or {}).get("user_agent")

    @admin.display(description=_("URL"))
    def get_url(self, obj: ClientEventProxy) -> Any | None:
        return (obj.pgh_context or {}).get("url")

    @admin.display(description=_("Метод"))
    def get_method(self, obj: ClientEventProxy) -> Any | None:
        return (obj.pgh_context or {}).get("method")

    @admin.display(description=_("Celery задача"))
    def get_celery_task(self, obj: ClientEventProxy) -> Any | None:
        return (obj.pgh_context or {}).get("celery_task")

    @admin.display(description=_("CLI команда"))
    def get_command(self, obj: ClientEventProxy) -> Any | None:
        return (obj.pgh_context or {}).get("command")

    @admin.display(description=_("Изменения"))
    def short_diff(self, obj: ClientEventProxy) -> str:
        """Читаемый короткий diff (без JSON-каши) прямо в list_display."""
        if not getattr(obj, "pgh_diff", None):
            return "—"

        parts: list[str] = []

        for field, (old, new) in obj.pgh_diff.items():
            parts.append(f"{field}: {old} → {new}")

        return "; ".join(parts[:3])  # Ограничиваем длину

    @admin.display(description=_("Тип"))
    def colored_label(self, obj: ClientEventProxy) -> str:
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

    # --- Делаем историю неизменяемой (Read-only) ---

    def has_add_permission(self, request: HttpRequest) -> bool:
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False

    def has_delete_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False


# ---------------------------------------------------------
# Client admin
# ---------------------------------------------------------


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
        "created_at",
        "updated_at",
        "deleted_at",
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
                    "created_at",
                    "updated_at",
                    "deleted_at",
                )
            },
        ),
        (
            _("Команда и учет"),
            {"fields": ("tax_system", "accountant", "primary_accountant", "payroll_accountant", "hr_specialist")},
        ),
        (_("Контакты и интеграции"), {"fields": ("contact_info", "google_folder_id")}),
    )

    readonly_fields = ("created_at", "updated_at", "deleted_at")

    # Автокомплит (поиск в выпадающем списке), чтобы список не тормозил, если юзеров станет много
    autocomplete_fields = (
        "accountant",
        "primary_accountant",
        "payroll_accountant",
        "hr_specialist",
    )
