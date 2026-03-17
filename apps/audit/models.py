"""
Модель для журнала аудита.
"""

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from pghistory import ProxyField
from pghistory.models import Events


class KrononEvents(Events):
    """Расширенная прокси-модель для отображения полей контекста истории изменений в админке."""

    # Пользователь
    user = ProxyField(
        "pgh_context__user",
        models.ForeignKey(
            settings.AUTH_USER_MODEL,
            null=True,
            blank=True,
            # Если пользователя удалят физически, история должна остаться
            on_delete=models.DO_NOTHING,
            # Отключаем constraint БД, чтобы не было ошибки целостности при удалении родителя
            db_constraint=False,
            verbose_name=_("Пользователь"),
            help_text=_("Сотрудник, внесший изменения"),
        ),
    )

    # Исторический Email из контекста (спасет, если юзера удалят из БД)
    user_email = ProxyField(
        "pgh_context__user_email",
        models.CharField(
            max_length=254,
            null=True,
            blank=True,
            verbose_name=_("Email пользователя"),
            help_text=_("Для исторических данных (полезно если пользователь был удален)"),
        ),
    )

    # ID корреляции
    correlation_id = ProxyField(
        "pgh_context__correlation_id", models.UUIDField(null=True, blank=True, verbose_name=_("ID корреляции"))
    )

    # IP адрес
    ip_address = ProxyField(
        "pgh_context__ip_address",
        models.GenericIPAddressField(null=True, blank=True, verbose_name=_("IP адрес")),
    )

    # User-Agent
    user_agent = ProxyField(
        "pgh_context__user_agent",
        models.CharField(max_length=255, null=True, blank=True, verbose_name=_("User-Agent")),
    )

    # URL запроса
    url = ProxyField(
        "pgh_context__url",
        models.TextField(null=True, blank=True, verbose_name=_("URL")),
    )

    # HTTP метод
    method = ProxyField(
        "pgh_context__method",
        models.CharField(max_length=10, null=True, blank=True, verbose_name=_("HTTP метод")),
    )

    # Сервис - источник изменения объекта (API/Web, Celery, CLI)
    service = ProxyField(
        "pgh_context__service",
        models.CharField(max_length=50, null=True, blank=True, verbose_name=_("Сервис")),
    )

    # Для Celery (название задачи)
    celery_task_name = ProxyField(
        "pgh_context__celery_task_name",
        models.TextField(null=True, blank=True, verbose_name=_("Название Celery-задачи")),
    )

    # Для Celery (ID задачи)
    celery_task_id = ProxyField(
        "pgh_context__celery_task_id",
        models.UUIDField(null=True, blank=True, verbose_name=_("ID Celery-задачи")),
    )

    # Для CLI (команда в manage.py)
    cli_command = ProxyField(
        "pgh_context__cli_command",
        models.TextField(null=True, blank=True, verbose_name=_("CLI команда")),
    )

    class Meta:
        proxy = True
        verbose_name = _("Журнал изменений")
        verbose_name_plural = _("Журнал изменений")
        ordering = ["-pgh_created_at"]
