"""
Админка для клиентов.
"""

from typing import Any

from django.contrib import admin
from django.http import HttpRequest
from django.utils.translation import gettext_lazy as _

from apps.clients.models import Client
from apps.common.admin import KrononBaseAdmin


@admin.register(Client)
class ClientAdmin(KrononBaseAdmin[Client]):
    """Управление клиентами."""

    list_display = (
        "name",
        "unp",
        "soft_delete_status",
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

    list_display_links = ("name",)

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

    # Кастомный SoftDeleteFilter фильтр + базовые фильтры
    def get_list_filter(self, request: HttpRequest) -> Any:
        """Расширяет фильтрацию списка."""

        soft_delete_filter = super().get_list_filter(request)  # type: ignore[no-untyped-call]

        filters = (
            "status",
            "department",
            "org_type",
            "tax_system",
            "accountant",
            "primary_accountant",
            "payroll_accountant",
            "hr_specialist",
        )

        return soft_delete_filter + filters
