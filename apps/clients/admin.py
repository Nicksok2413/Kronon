"""
Админка для клиентов и журнала аудита.
"""

# from typing import Any

from django.contrib import admin

# from django.db.models import QuerySet
# from django.http import HttpRequest
# from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

# from pghistory.admin import EventModelAdmin
from rangefilter.filters import DateTimeRangeFilter

from apps.clients.models.client import Client
from apps.clients.models.client_event import ClientEventProxy

# ---------------------------------------------------------
# Client history admin
# ---------------------------------------------------------


@admin.register(ClientEventProxy)
class ClientEventAdmin(admin.ModelAdmin):
    """
    Админка для просмотра аудита изменений (History).
    Работает с ProxyFields и ContextJSONField.
    """

    list_display = [
        "pgh_created_at",
        "pgh_label",
        # "colored_label",
        # "get_client_info",
        # "short_diff",
        # "get_user_info",
        "get_user_id",
        "get_user_email",
        "get_app_source",
        "get_ip_address",
        "get_user_agent",
    ]

    list_filter = [
        "pgh_label",
        ("pgh_created_at", DateTimeRangeFilter),  # Фильтрация по дате (UI с календарём) на уровне БД
        # "get_app_source",
    ]

    # Поиск по имени/унп клиента, email автора изменений и по IP адресу
    search_fields = (
        # "pgh_obj__name",
        # "pgh_obj__unp",
        "get_user_email",
        "get_ip_address",
    )

    # ordering = ("-pgh_created_at",)

    # # Делаем JOIN клиента и пользователя, чтобы не было N+1 запросов при отрисовке списка
    # list_select_related = ("pgh_obj", "user")
    #
    # # Явно запрещаем массовые действия
    # actions = None

    # Немного ускорит админку на больших объёмах
    list_per_page = 50

    # # def get_queryset(self, request: HttpRequest) -> QuerySet[ClientEventProxy]:
    # #     """
    # #     Переопределяем метод получения queryset.
    # #     Django по умолчанию тянет тяжелый pgh_data.
    # #     Откладываем (.defer) загрузку pgh_data, так как не используем его в list_display.
    # #     Это дает буст к производительности.
    # #     """
    # #     queryset = super().get_queryset(request)
    # #     return queryset.defer("pgh_data")
    #
    # # --- UI helpers & ProxyField методы ---
    #
    # @admin.display(description=_("Пользователь"), ordering="user_email")
    # def get_user_info(self, obj: ClientEventProxy) -> str:
    #     """Показывает ФИО и Email автора изменения клиента (или Email из контекста, если удален)."""
    #     # Если юзер есть в БД - берем его актуальные данные
    #     if obj.user:
    #         # user_obj = User.objects.aget(pk=obj.user)
    #         # url = reverse("admin:%s_%s_change" % (User._meta.app_label, User._meta.model_name), args=[obj.user])
    #         # return format_html("<a href='{}'>{}</a>", url, obj.user.full_name_rus() or obj.user.email)
    #         return f"{obj.user.full_name_rus} ({obj.user.email})"
    #
    #     # Если юзера удалили, берем email из JSON-слепка истории
    #     if obj.user_email:
    #         return f"Удален ({obj.user_email})"
    #
    #     return "System / Unknown"
    #
    # @admin.display(description=_("Тип"))
    # def colored_label(self, obj: ClientEventProxy) -> str:
    #     """
    #     Цветовая индикация типов событий.
    #
    #     Зеленый - Создание нового клиента.
    #     Оранжевый - Обновление клиента.
    #     Красный - Удаление клиента.
    #     Черный - По умолчанию.
    #     """
    #     colors = {
    #         "insert": "green",
    #         "update": "orange",
    #         "delete": "red",
    #     }
    #     color = colors.get(obj.pgh_label, "black")
    #     return format_html('<b style="color:{}">{}</b>', color, obj.pgh_label)
    #
    # @admin.display(description=_("Изменения"))
    # def short_diff(self, obj: ClientEventProxy) -> str:
    #     """Читаемый короткий diff (без JSON-каши) прямо в list_display."""
    #     if not getattr(obj, "pgh_diff", None):
    #         return "—"
    #
    #     parts: list[str] = []
    #
    #     for field, (old, new) in obj.pgh_diff.items():
    #         parts.append(f"{field}: {old} → {new}")
    #
    #     return "; ".join(parts[:3])  # Ограничиваем длину
    #
    # @admin.display(description=_("Клиент (Snapshot)"))
    # def get_client_id(self, obj: ClientEventProxy) -> str:
    #     """Отображает информацию об клиенте на момент события."""
    #     client_name = obj.pgh_context.get("pgh_obj__name", "") or "—"
    #     client_unp = obj.pgh_context.get("pgh_obj__unp", "") or "—"
    #     return f"{client_name} ({client_unp})"

    @admin.display(description="User ID")
    def get_user_id(self, obj: ClientEventProxy) -> str:
        ctx = obj.pgh_context or {}
        return ctx.get("user") or "—"

    @admin.display(description="User Email")
    def get_user_email(self, obj: ClientEventProxy) -> str:
        ctx = obj.pgh_context or {}
        return ctx.get("user_email") or "—"

    @admin.display(description=_("Источник"))
    def get_app_source(self, obj: ClientEventProxy) -> str:
        ctx = obj.pgh_context or {}
        return ctx.get("app_source") or "—"

    @admin.display(description=_("IP адрес"))
    def get_ip_address(self, obj: ClientEventProxy) -> str:
        ctx = obj.pgh_context or {}
        return ctx.get("ip_address") or "—"

    @admin.display(description=_("User-Agent"))
    def get_user_agent(self, obj: ClientEventProxy) -> str:
        ctx = obj.pgh_context or {}
        return ctx.get("user_agent") or "—"

    @admin.display(description=_("Метод"))
    def get_method(self, obj: ClientEventProxy) -> str:
        ctx = obj.pgh_context or {}
        return ctx.get("method") or "—"

    @admin.display(description=_("URL"))
    def get_url(self, obj: ClientEventProxy) -> str:
        ctx = obj.pgh_context or {}
        return ctx.get("url") or "—"

    @admin.display(description=_("Celery Task"))
    def get_celery_task(self, obj: ClientEventProxy) -> str:
        ctx = obj.pgh_context or {}
        return ctx.get("celery_task") or "—"

    @admin.display(description=_("Команда"))
    def get_command(self, obj: ClientEventProxy) -> str:
        ctx = obj.pgh_context or {}
        return ctx.get("command") or "—"

    # # --- Делаем историю неизменяемой (Read-only) ---
    #
    # def has_add_permission(self, request: HttpRequest) -> bool:
    #     return False
    #
    # def has_change_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
    #     return False
    #
    # def has_delete_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
    #     return False


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
