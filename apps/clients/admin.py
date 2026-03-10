"""
Админка для клиентов и журнала аудита.
"""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from rangefilter.filters import DateTimeRangeFilter

from apps.clients.models.client import Client
from apps.clients.models.client_event import ClientEvent

# ---------------------------------------------------------
# Inline history в карточке клиента
# ---------------------------------------------------------


class ClientEventInline(admin.TabularInline[ClientEvent, Client]):
    """
    Инлайн для отображения истории в карточке клиента.
    Работает с ProxyFields и денормализованным контекстом.
    """

    model = ClientEvent
    # fk_name = "pgh_obj"  # это ForeignKey на Client, созданный pghistory
    extra = 0
    can_delete = False
    readonly_fields = (
        "pgh_created_at",
        "pgh_label",
        "get_user_info",
        "get_app_source",
        "get_ip_address",
        "get_user_agent",
        "get_method",
        "get_url",
        "get_celery_task",
        "get_command",
    )
    verbose_name_plural = _("События")
    ordering = ("-pgh_created_at",)

    # def get_queryset(self, request: HttpRequest) -> QuerySet[ClientEvent]:
    #     """Переопределяем метод для подгрузки пользователя через ProxyField (чтобы не было N+1 запросов)."""
    #     return super().get_queryset(request).select_related("user")

    # --- UI helpers & ProxyField методы ---

    # @admin.display(description=_("Пользователь"), ordering="user_email")
    # def get_user_info(self, obj: ClientEvent) -> str:
    #     """Показывает ФИО и Email автора изменения клиента (или Email из контекста, если удален)."""
    #     # Если юзер есть в БД - берем его актуальные данные
    #     if obj.user:
    #         try:
    #             user_obj = User.objects.aget(pk=obj.user)
    #             url = reverse("admin:%s_%s_change" % (User._meta.app_label, User._meta.model_name), args=[obj.user])
    #             return format_html("<a href='{}'>{}</a>", url, user_obj.full_name_rus() or user_obj.email)
    #         except User.DoesNotExist:
    #             return obj.user_email
    #
    #     # Если юзера удалили, берем email из JSON-слепка истории
    #     if obj.user_email:
    #         return f"Удален ({obj.user_email})"
    #
    #     return "System / Unknown"

    @admin.display(description=_("Источник"))
    def get_app_source(self, obj: ClientEvent) -> str:
        return getattr(obj, "app_source", "") or "—"

    @admin.display(description=_("IP адрес"))
    def get_ip_address(self, obj: ClientEvent) -> str:
        return getattr(obj, "ip_address", "") or "—"

    @admin.display(description=_("User-Agent"))
    def get_user_agent(self, obj: ClientEvent) -> str:
        return getattr(obj, "user_agent", "") or "—"

    @admin.display(description=_("Метод"))
    def get_method(self, obj: ClientEvent) -> str:
        return getattr(obj, "method", "") or "—"

    @admin.display(description=_("URL"))
    def get_url(self, obj: ClientEvent) -> str:
        return getattr(obj, "url", "") or "—"

    @admin.display(description=_("Celery Task"))
    def get_celery_task(self, obj: ClientEvent) -> str:
        return getattr(obj, "celery_task", "") or "—"

    @admin.display(description=_("Команда"))
    def get_command(self, obj: ClientEvent) -> str:
        return getattr(obj, "command", "") or "—"

    def has_add_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        return False


@admin.register(ClientEvent)
class ClientEventAdmin(admin.ModelAdmin[ClientEvent]):
    """
    Админка для просмотра аудита изменений (History).
    Работает без pgh_data, с ProxyFields и ContextJSONField.
    """

    list_display = [
        "pgh_created_at",
        "colored_label",
        "get_client_info",
        "short_diff",  # Читаемый короткий Diff
        "get_user_info",
        "get_app_source",
        "get_ip_address",
        "get_user_agent",
    ]

    list_filter = [
        "pgh_label",
        ("pgh_created_at", DateTimeRangeFilter),  # Фильтрация по дате (UI с календарём) на уровне БД
        "app_source",
    ]

    # Делаем JOIN таблицы пользователей, чтобы не было N+1 запросов при отрисовке списка
    # list_select_related = ("pgh_context__user",)

    # Поиск по имени/унп клиента, email автора изменений и по IP адресу
    search_fields = (
        "name",
        "unp",
        "user_email",
        "ip_address",
    )

    readonly_fields = (
        "pgh_created_at",
        "pgh_label",
        "get_client_info",
        "short_diff",
        "get_user_info",
        "get_app_source",
        "get_ip_address",
        "get_user_agent",
        "get_method",
        "get_url",
        "get_celery_task",
        "get_command",
    )

    ordering = ("-pgh_created_at",)

    # Явно запрещаем массовые действия
    actions = None

    # Немного ускорит админку на больших объёмах
    list_per_page = 50

    # def get_queryset(self, request: HttpRequest) -> QuerySet[ClientEvent]:
    #     """Переопределяем метод для подгрузки пользователя через ProxyField (чтобы не было N+1 запросов)."""
    #     return super().get_queryset(request).select_related("user")

    # --- UI helpers & ProxyField методы ---

    # @admin.display(description=_("Пользователь"), ordering="user_email")
    # def get_user_info(self, obj: ClientEvent) -> str:
    #     """Показывает ФИО и Email автора изменения клиента (или Email из контекста, если удален)."""
    #     # Если юзер есть в БД - берем его актуальные данные
    #     if obj.user:
    #         try:
    #             user_obj = User.objects.aget(pk=obj.user)
    #             url = reverse("admin:%s_%s_change" % (User._meta.app_label, User._meta.model_name), args=[obj.user])
    #             return format_html("<a href='{}'>{}</a>", url, user_obj.full_name_rus() or user_obj.email)
    #         except User.DoesNotExist:
    #             return obj.user_email
    #
    #     # Если юзера удалили, берем email из JSON-слепка истории
    #     if obj.user_email:
    #         return f"Удален ({obj.user_email})"
    #
    #     return "System / Unknown"

    @admin.display(description=_("Тип"))
    def colored_label(self, obj: ClientEvent) -> str:
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
    def short_diff(self, obj: ClientEvent) -> str:
        """Читаемый короткий diff (без JSON-каши) прямо в list_display."""
        if not getattr(obj, "pgh_diff", None):
            return "—"

        parts: list[str] = []

        for field, (old, new) in obj.pgh_diff.items():
            parts.append(f"{field}: {old} → {new}")

        return "; ".join(parts[:3])  # Ограничиваем длину

    @admin.display(description=_("Клиент (Snapshot)"))
    def get_client_info(self, obj: ClientEvent) -> str:
        """Отображает информацию об клиенте на момент события."""
        return f"{obj.name} ({obj.unp})"

    @admin.display(description=_("Источник"))
    def get_app_source(self, obj: ClientEvent) -> str:
        return getattr(obj, "app_source", "") or "—"

    @admin.display(description=_("IP адрес"))
    def get_ip_address(self, obj: ClientEvent) -> str:
        return getattr(obj, "ip_address", "") or "—"

    @admin.display(description=_("User-Agent"))
    def get_user_agent(self, obj: ClientEvent) -> str:
        return getattr(obj, "user_agent", "") or "—"

    @admin.display(description=_("Метод"))
    def get_method(self, obj: ClientEvent) -> str:
        return getattr(obj, "method", "") or "—"

    @admin.display(description=_("URL"))
    def get_url(self, obj: ClientEvent) -> str:
        return getattr(obj, "url", "") or "—"

    @admin.display(description=_("Celery Task"))
    def get_celery_task(self, obj: ClientEvent) -> str:
        return getattr(obj, "celery_task", "") or "—"

    @admin.display(description=_("Команда"))
    def get_command(self, obj: ClientEvent) -> str:
        return getattr(obj, "command", "") or "—"

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
