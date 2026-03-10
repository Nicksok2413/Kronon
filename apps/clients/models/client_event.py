"""
Модели для аудита клиентов.
"""

import pghistory
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.clients.models.client import Client

# Создаем базовый класс для модели событий (аналог декоратора pghistory.track)
BaseClientEvent = pghistory.create_event_model(
    Client,
    pghistory.InsertEvent(),
    pghistory.UpdateEvent(),
    pghistory.DeleteEvent(),
    # Явно задаем имя модели событий и имя связи
    model_name="ClientEvent",
    obj_field=pghistory.ObjForeignKey(
        related_name="events",
        # Если клиента удалят физически, история должна остаться
        on_delete=models.DO_NOTHING,
        # Отключаем constraint БД, чтобы не было ошибки целостности при удалении родителя
        db_constraint=False,
    ),
)


class ClientEvent(BaseClientEvent):  # type: ignore[valid-type, misc]
    """
    Модель для хранения истории изменений клиентов.

    Использует pghistory.ProxyField для удобного доступа к JSON-контексту в админке.
    """

    # --- Проксируем поля из контекста ---

    # ID пользователя
    user = pghistory.ProxyField(
        "pgh_context__user",
        models.UUIDField(null=True, blank=True, verbose_name=_("Пользователь")),
    )

    # Email пользователя
    user_email = pghistory.ProxyField(
        "pgh_context__user_email",
        models.CharField(max_length=254, null=True, blank=True, verbose_name=_("Email пользователя (исторический)")),
    )

    # Источник изменения (API/Web, Celery, CLI)
    app_source = pghistory.ProxyField(
        "pgh_context__app_source",
        models.CharField(max_length=50, null=True, blank=True, verbose_name=_("Источник изменения")),
    )

    # IP адрес
    ip_address = pghistory.ProxyField(
        "pgh_context__ip_address",
        models.GenericIPAddressField(null=True, blank=True, verbose_name=_("IP Адрес")),
    )

    # User-Agent
    user_agent = pghistory.ProxyField(
        "pgh_context__user_agent",
        models.GenericIPAddressField(null=True, blank=True, verbose_name=_("User-Agent")),
    )

    # HTTP метод
    method = pghistory.ProxyField(
        "pgh_context__method",
        models.CharField(max_length=10, null=True, blank=True, verbose_name=_("HTTP Метод")),
    )

    # URL запроса
    url = pghistory.ProxyField(
        "pgh_context__url",
        models.TextField(null=True, blank=True, verbose_name=_("URL")),
    )

    # Для Celery
    celery_task = pghistory.ProxyField(
        "pgh_context__celery_task",
        models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Celery Task")),
    )

    # Для CLI (manage.py)
    command = pghistory.ProxyField(
        "pgh_context__command",
        models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Команда")),
    )

    class Meta:
        verbose_name = _("Журнал изменений клиента")
        verbose_name_plural = _("Журнал изменений клиентов")
        ordering = ["-pgh_created_at"]
