"""
Админка для клиентов и журнала аудита.
"""

import json
from typing import Any

from django.contrib import admin

# from django.db.models import QuerySet
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

# from pghistory.admin import EventModelAdmin
from rangefilter.filters import DateTimeRangeFilter

from apps.clients.models import Client, ClientEventProxy

# ---------------------------------------------------------
# Client history admin
# ---------------------------------------------------------


@admin.register(ClientEventProxy)
class ClientEventAdmin(admin.ModelAdmin[ClientEventProxy]):
    """
    Админка для просмотра аудита изменений (History).
    Работает с ProxyFields и ContextJSONField.
    """

    # date_hierarchy = "pgh_created_at"

    list_display = [
        "pgh_created_at",
        # "pgh_diff",
        "get_client",
        "colored_label",
        # "get_client_info",
        "short_diff",
        # "get_user_info",
        # "get_user_id",
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
        # "get_app_source",
    ]

    # Поиск по имени/унп клиента, email автора изменений и по IP адресу
    search_fields = ("pgh_context",)

    readonly_fields = (
        # "pgh_diff",
        "pgh_created_at",
        "pgh_label",
        "pgh_context",
    )

    # # Делаем JOIN клиента, чтобы не было N+1 запросов при отрисовке списка
    list_select_related = ("pgh_obj",)

    # Явно запрещаем массовые действия
    actions = None

    # Немного ускорит админку на больших объёмах
    list_per_page = 10

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
    #
    # @admin.display(description=_("Клиент (Snapshot)"))
    # def get_client_id(self, obj: ClientEventProxy) -> str:
    #     """Отображает информацию об клиенте на момент события."""
    #     client_name = obj.pgh_context.get("pgh_obj__name", "") or "—"
    #     client_unp = obj.pgh_context.get("pgh_obj__unp", "") or "—"
    #     return f"{client_name} ({client_unp})"

    # --- UI helpers ---

    @admin.display(description="Клиент")
    def get_client(self, obj: ClientEventProxy) -> Client:
        return obj.pgh_obj

    @admin.display(description="ID пользователя")
    def get_user_id(self, obj: ClientEventProxy) -> str:
        return (obj.pgh_context or {}).get("user")

    @admin.display(description="Email пользователя")
    def get_user_email(self, obj: ClientEventProxy) -> str:
        return (obj.pgh_context or {}).get("user_email")

    @admin.display(description=_("Источник"))
    def get_app_source(self, obj: ClientEventProxy) -> str:
        return (obj.pgh_context or {}).get("app_source")

    @admin.display(description=_("IP адрес"))
    def get_ip_address(self, obj: ClientEventProxy) -> str:
        return (obj.pgh_context or {}).get("ip_address")

    @admin.display(description=_("User-Agent"))
    def get_user_agent(self, obj: ClientEventProxy) -> str:
        return (obj.pgh_context or {}).get("user_agent")

    @admin.display(description=_("URL"))
    def get_url(self, obj: ClientEventProxy) -> str:
        return (obj.pgh_context or {}).get("url")

    @admin.display(description=_("Метод"))
    def get_method(self, obj: ClientEventProxy) -> str:
        return (obj.pgh_context or {}).get("method")

    @admin.display(description=_("Celery задача"))
    def get_celery_task(self, obj: ClientEventProxy) -> str:
        return (obj.pgh_context or {}).get("celery_task")

    @admin.display(description=_("CLI команда"))
    def get_command(self, obj: ClientEventProxy) -> str:
        return (obj.pgh_context or {}).get("command")

    def context_json(self, obj):
        return json.dumps(obj.pgh_context or {}, indent=2)

    @admin.display(description=_("Изменения"))
    def short_diff(self, obj: ClientEventProxy) -> str:
        """Читаемый короткий diff (без JSON-каши) прямо в list_display."""
        if not getattr(obj, "pgh_diff", None):
            return "—"

        parts: list[str] = []

        for field, (old, new) in obj.pgh_diff.items():
            parts.append(f"{field}: {old} → {new}")

        return "; ".join(parts[:3])  # Ограничиваем длину

        # prev = (
        #     obj.__class__.objects.filter(
        #         pgh_obj=obj.pgh_obj,
        #         pgh_created_at__lt=obj.pgh_created_at,
        #     )
        #     .order_by("-pgh_created_at")
        #     .first()
        # )
        #
        # if not prev:
        #     return "—"
        #
        # diff = {}
        #
        # for field in obj._meta.fields:
        #     name = field.name
        #
        #     if name.startswith("pgh_"):
        #         continue
        #
        #     old = getattr(prev, name)
        #     new = getattr(obj, name)
        #
        #     if old != new:
        #         diff[name] = (old, new)
        #
        # return json.dumps(diff, indent=2)

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
