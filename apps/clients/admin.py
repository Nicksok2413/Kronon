"""
Админка для клиентов.
"""

import pghistory
from django.contrib import admin
from django.db import models
from django.http import HttpRequest
from pghistory.admin import EventModelAdmin

from apps.clients.models import Client


# Создаем прокси для глобальной модели Events, но отфильтрованной по Клиентам
# Это позволяет использовать мощь pgh_diff
class ClientEventProxy(pghistory.models.Events):
    """
    Прокси-модель для отображения агрегированных событий Клиента.
    Позволяет видеть DIFF (разницу) изменений.
    """

    # Проксируем поля из JSON-контекста
    user_email = pghistory.ProxyField(
        "pgh_context__user_email",
        models.CharField(max_length=255, verbose_name="Email (Context)"),
    )
    ip_address = pghistory.ProxyField(
        "pgh_context__ip",
        models.GenericIPAddressField(verbose_name="IP"),
    )

    class Meta:
        proxy = True
        verbose_name = "Аудит клиента"
        verbose_name_plural = "Аудит клиентов"


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
    Админка истории изменений.
    """

    # pgh_diff - киллер-фича агрегированной модели Events
    list_display = ["pgh_created_at", "client_info", "pgh_label", "user_email", "pgh_diff"]
    list_filter = ["pgh_label", "pgh_obj_model"]

    # Поиск по проксированным полям
    search_fields = ["user_email", "ip_address"]

    @staticmethod
    def client_info(self, obj) -> str:
        # pgh_obj_id хранит ID объекта (UUID)
        return f"Client {obj.pgh_obj_id}"

    # Ограничиваем выборку только событиями Клиентов
    def get_queryset(self, request: HttpRequest):
        return super().get_queryset(request).across(Client)
