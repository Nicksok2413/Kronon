"""
Модели для аудита клиентов.
"""

# import pghistory
# from django.contrib.auth import get_user_model
# from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.clients.models.client import Client

# User = get_user_model()


class ClientEventProxy(Client.pgh_event_model):  # type: ignore[valid-type, misc]
    """
    Прокси-модель истории изменений клиентов, предоставляющая поля JSON-контекста в виде структурированных столбцов.

    Использует pghistory.ProxyField для удобного доступа к JSON-контексту в админке.

    Так как включена денормализация контекста `PGHISTORY_CONTEXT_FIELD = ContextJSONField()`,
    пути к полям: pgh_context__<field>
    """

    # objects = models.Manager()

    # --- Проксируем поля из контекста ---

    # # Проксируем пользователя как Foreign Key (Django сделает LEFT JOIN в админке автоматически)
    # # Это позволяет обращаться к user.email так, будто это настоящая SQL связь
    # user = pghistory.ProxyField(
    #     "pgh_context__user",
    #     models.ForeignKey(
    #         User,
    #         null=True,
    #         blank=True,
    #         # Если пользователя удалят физически, история должна остаться
    #         on_delete=models.DO_NOTHING,
    #         # Отключаем constraint БД, чтобы не было ошибки целостности при удалении родителя
    #         db_constraint=False,
    #         related_name="+",
    #         verbose_name=_("Пользователь"),
    #         help_text=_("Сотрудник, внесший изменения"),
    #     ),
    # )
    # user_id = pghistory.ProxyField(
    #     "pgh_context__user",
    #     models.UUIDField(
    #         null=True,
    #         blank=True,
    #         verbose_name=_("Пользователь"),
    #         help_text=_("Сотрудник, внесший изменения"),
    #     ),
    # )
    #
    # # Неизменяемый слепок Email пользователя из контекста (спасет, если юзера удалят из БД)
    # user_email = pghistory.ProxyField(
    #     "pgh_context__user_email",
    #     models.CharField(max_length=254, null=True, blank=True, verbose_name=_("Email пользователя (исторический)")),
    # )
    #
    # # Источник изменения (API/Web, Celery, CLI)
    # app_source = pghistory.ProxyField(
    #     "pgh_context__app_source",
    #     models.CharField(max_length=50, null=True, blank=True, verbose_name=_("Источник изменения")),
    # )
    #
    # # IP адрес
    # ip_address = pghistory.ProxyField(
    #     "pgh_context__ip_address",
    #     models.GenericIPAddressField(null=True, blank=True, verbose_name=_("IP Адрес")),
    # )
    #
    # # User-Agent
    # user_agent = pghistory.ProxyField(
    #     "pgh_context__user_agent",
    #     models.TextField(null=True, blank=True, verbose_name=_("User-Agent")),
    # )
    #
    # # HTTP метод
    # method = pghistory.ProxyField(
    #     "pgh_context__method",
    #     models.CharField(max_length=10, null=True, blank=True, verbose_name=_("HTTP Метод")),
    # )
    #
    # # URL запроса
    # url = pghistory.ProxyField(
    #     "pgh_context__url",
    #     models.TextField(null=True, blank=True, verbose_name=_("URL")),
    # )
    #
    # # Для Celery
    # celery_task = pghistory.ProxyField(
    #     "pgh_context__celery_task",
    #     models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Celery Task")),
    # )
    #
    # # Для CLI (manage.py)
    # command = pghistory.ProxyField(
    #     "pgh_context__command",
    #     models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Команда")),
    # )

    class Meta:
        proxy = True
        verbose_name = _("Журнал изменений клиента")
        verbose_name_plural = _("Журнал изменений клиентов")
