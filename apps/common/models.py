"""
Общие модели для всего проекта.
"""

import uuid
from typing import Any

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from pghistory.core import ProxyField
from pghistory.models import Events

from apps.common.managers import SoftDeleteManager


class TimeStampedModel(models.Model):
    """
    Абстрактная модель с таймстэмпами (датами создания/обновления).

    Используется там, где не нужен UUIDv7 PK или SoftDelete (например, Profile, M2M таблицы).
    """

    created_at = models.DateTimeField(
        _("Дата создания"),
        auto_now_add=True,
        editable=False,
    )
    updated_at = models.DateTimeField(
        _("Дата обновления"),
        auto_now=True,
        editable=False,
    )

    class Meta:
        abstract = True


class BaseModel(TimeStampedModel):
    """
    Основная базовая модель для бизнес-сущностей (Clients, Contracts, etc).

    Наследует таймстэмпы от TimeStampedModel.

    Добавляет:
    1. UUIDv7 в качестве первичного ключа (сортируемый).
    2. Логику мягкого удаления (Soft Delete).
    """

    # Используем UUIDv7 для сортируемых уникальных ID
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid7,
        editable=False,
        verbose_name="ID",
    )

    # Поле мягкого удаления
    deleted_at = models.DateTimeField(
        _("Дата удаления"),
        null=True,
        blank=True,
        editable=False,
        db_index=True,  # Индекс нужен, так как часто будет фильтрация по IS NULL
    )

    # Кастомный менеджер для мягкого удаления (по умолчанию для всех моделей, наследующих BaseModel)
    objects = SoftDeleteManager()

    # Стандартный менеджер для чистого поведения (опционально)
    all_objects = models.Manager()

    class Meta:
        abstract = True
        # Сортировка по умолчанию (обратный порядок - новые сверху)
        # UUIDv7 сортируется по времени быстрее, чем created_at
        ordering = ["-id"]

    @property
    def is_deleted(self) -> bool:
        """Удобное свойство для проверки статуса."""
        return self.deleted_at is not None

    async def adelete(self, using: Any = None, keep_parents: bool = False) -> tuple[int, dict[str, int]]:
        """
        Мягкое удаление объекта.
        """
        now = timezone.now()
        self.deleted_at = now
        self.updated_at = now

        # Используем update_fields для оптимизации SQL запроса
        await self.asave(using=using, update_fields=["deleted_at", "updated_at"])
        return 1, {self._meta.label: 1}

    async def ahard_delete(self, **kwargs: Any) -> tuple[int, dict[str, int]]:
        """
        Физическое удаление объекта из БД.
        """
        return await super().adelete(**kwargs)

    async def arestore(self) -> None:
        """
        Восстановление удаленного объекта.
        """
        now = timezone.now()
        self.deleted_at = None
        self.updated_at = now

        # Используем update_fields для оптимизации SQL запроса
        await self.asave(update_fields=["deleted_at", "updated_at"])


class KrononEvents(Events):
    """Расширенная прокси-модель отображения полей контекста истории изменений в админке."""

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
    celery_task = ProxyField(
        "pgh_context__celery_task",
        models.CharField(max_length=255, null=True, blank=True, verbose_name=_("Celery задача")),
    )

    # Для CLI (команда в manage.py)
    command = ProxyField(
        "pgh_context__command",
        models.CharField(max_length=255, null=True, blank=True, verbose_name=_("CLI команда")),
    )

    class Meta:
        proxy = True
        verbose_name = _("Журнал изменений клиента")
        verbose_name_plural = _("Журнал изменений клиентов")
        ordering = ["-pgh_created_at"]
