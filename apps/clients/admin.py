"""
Админка для клиентов и журнала аудита.
"""

from django.contrib import admin
from pghistory.admin import EventModelAdmin

from apps.clients.models import Client, ClientEventProxy


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


@admin.register(ClientEventProxy)
class ClientEventAdmin(EventModelAdmin):
    """
    Админка для просмотра аудита изменений (History).
    Наследуется от EventModelAdmin для корректного отображения Diff.
    Работает с Proxy-моделью для доступа к полям контекста.
    """

    # Отображаем стандартные поля pghistory + прокси поля
    list_display = [
        "pgh_created_at",
        "pgh_label",
        "client_info",
        "user_email",  # Proxy field
        "ip_address",  # Proxy field
        "app_source",  # Proxy field
    ]

    list_filter = ["pgh_label", "app_source", "method"]

    # Поиск
    search_fields = [
        "pgh_obj__name",
        "pgh_obj__unp",
        "user_email",  # Proxy field
        "ip_address",  # Proxy field
    ]

    ordering = ["-pgh_created_at"]

    def client_info(self, obj: ClientEventProxy) -> str:
        """
        Отображает информацию об объекте (snapshot).

        Args:
            obj: Объект события.

        Returns:
            str: Строковое представление клиента на момент события.
        """
        return f"{obj.name} ({obj.unp})"

    client_info.short_description = "Клиент (Snapshot)"
