"""
Базовая абстрактная модель.

Все бизнес-сущности наследуются от неё.
"""

import uuid
from typing import Any

from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.managers import SoftDeleteManager


class BaseModel(models.Model):
    """
    Базовая модель с UUIDv7 (в качестве первичного ключа), таймстэмпами и мягким удалением.
    """

    # Используем UUIDv7 для сортируемых уникальных ID
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid7,
        editable=False,
        verbose_name="ID",
    )

    created_at = models.DateTimeField(
        _("Дата создания"),
        auto_now_add=True,
        editable=False,
        db_index=True,  # Индекс для сортировок
    )

    updated_at = models.DateTimeField(
        _("Дата обновления"),
        auto_now=True,
        editable=False,
    )

    # Поле мягкого удаления
    deleted_at = models.DateTimeField(
        _("Дата удаления"),
        null=True,
        blank=True,
        editable=False,
        db_index=True,  # Индекс важен, так как часто будет фильтрация по IS NULL
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
