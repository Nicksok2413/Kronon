"""
Админка для клиентов и журнала аудита.
"""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest
from django.utils.html import format_html
from pghistory.admin import EventModelAdmin

from apps.clients.models import Client, ClientEvent


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
            "Основное",
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
            "Команда и Учет",
            {"fields": ("tax_system", "accountant", "primary_accountant", "payroll_accountant", "hr_specialist")},
        ),
        ("Контакты и Интеграции", {"fields": ("contact_info", "google_folder_id")}),
    )

    # Автокомплит (поиск в выпадающем списке), чтобы список не тормозил, если юзеров станет много
    autocomplete_fields = [
        "accountant",
        "primary_accountant",
        "payroll_accountant",
        "hr_specialist",
    ]


@admin.register(ClientEvent)
class ClientEventAdmin(EventModelAdmin):
    """
    Админка для просмотра аудита изменений (History).
    Наследуется от EventModelAdmin для корректного отображения Diff.
    """

    # Отображаем стандартные поля pghistory + прокси поля
    list_display = [
        "pgh_created_at",
        "pgh_label",
        "client_info",
        "get_user_info",  # Используем проксированный FK
        "app_source",
        "ip_address",
    ]

    list_filter = ["pgh_label", "app_source"]

    # Делаем JOIN таблицы пользователей, чтобы не было N+1 запросов при отрисовке списка
    # list_select_related = ["user"]
    list_select_related = ["pgh_context__user"]

    # Поиск по имени/унп клиента, email автора изменений и по IP адресу
    search_fields = [
        "pgh_obj__name",
        "pgh_obj__unp",
        "user__email",  # Поиск через FK работает нативно
        "user_email",  # Поиск по JSON на случай удаленного юзера
        "ip_address",
    ]

    # Явно запрещаем массовые действия
    actions = None

    # Немного ускорит админку на больших объёмах
    list_per_page = 50

    ordering = ["-pgh_created_at"]

    @admin.display(description="Клиент (Snapshot)")
    def client_info(self, obj: ClientEvent) -> str:
        """
        Отображает информацию об клиенте.

        Args:
            obj: Объект события.

        Returns:
            str: Строковое представление клиента на момент события.
        """
        return f"{obj.name} ({obj.unp})"

    @admin.display(description="Автор изменения", ordering="user__email")
    def get_user_info(self, obj: ClientEvent) -> str:
        """
        Показывает ФИО и Email автора изменения клиента (или Email из контекста, если удален).

        Args:
            obj: Объект события.

        Returns:
            str: Строковое представление автора изменения клиента.
        """
        # Если юзер есть в БД - берем его актуальные данные
        if obj.user_id and obj.user:
            return f"{obj.user.full_name_rus} ({obj.user.email})"

        # Если юзера удалили, берем email из JSON-слепка истории
        if obj.user_email:
            return f"Удален ({obj.user_email})"

        return "System / Unknown"

    @admin.display(description="Тип")
    def colored_label(self, obj: ClientEvent):
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
