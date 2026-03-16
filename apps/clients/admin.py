"""
Админка для клиентов.
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from apps.clients.models import Client


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
