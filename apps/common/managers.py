"""
Менеджер и QuerySet для реализации логики мягкого удаления (Soft Delete)
и нативной OLP-фильтрации.
"""

from typing import Self, TypeVar
from uuid import UUID

from django.db import models
from django.utils import timezone

from apps.users.constants import SYSTEM_USER_ID

# Определяем Generic переменную, ограниченную моделями Django
# Это позволяет mypy понимать, с какой именно моделью мы работаем
_M = TypeVar("_M", bound=models.Model)


class SoftDeleteQuerySet(models.QuerySet[_M]):
    """
    Кастомный QuerySet, реализующий логику мягкого удаления и OLP-фильтрацию.
    """

    def active(self) -> Self:
        """
        Возвращает только активные (не удаленные) записи.
        """
        return self.filter(deleted_at__isnull=True)

    def deleted(self) -> Self:
        """
        Возвращает только удаленные (находящиеся в корзине) записи.
        """
        return self.filter(deleted_at__isnull=False)

    def for_user(self, user_id: UUID, is_admin: bool = False) -> Self:
        """
        Нативная фильтрация прав доступа (OLP) на уровне БД.

        Args:
            user_id (UUID): ID инициатора запроса.
            is_admin (bool): Флаг наличия административных прав.

        Returns:
            Self: Отфильтрованный QuerySet.
        """
        # Системный доступ или наличие административных прав (админы, директор, главбух) - видят всё
        if is_admin or user_id == SYSTEM_USER_ID:
            return self

        # Для линейного персонала вызываем логику фильтрации из самой модели
        # Каждая модель, где нужна OLP-фильтрация (Client, Contract, etc) должна иметь метод get_olp_filter
        olp_method = getattr(self.model, "get_olp_filter", None)

        if olp_method:
            # Вызываем метод модели, который возвращает Q-объект
            olp_filter = olp_method(user_id)

            return self.filter(olp_filter).distinct()

        # Безопасный отказ: если OLP не настроен для модели — скрываем всё (пустой список)
        return self.none()

    async def adelete(self) -> tuple[int, dict[str, int]]:
        """
        Переопределение стандартного метода удаления (Bulk Delete).
        Вместо физического удаления проставляет текущее время в `deleted_at` и `updated_at`.

        Returns:
            tuple[int, dict[str, int]]: (Количество удаленных записей, Словарь по типам объектов).
            Формат совпадает со стандартным Django delete().
        """
        now = timezone.now()
        updated_count = await self.aupdate(deleted_at=now, updated_at=now)

        # Эмулируем возвращаемое значение стандартного delete()
        return updated_count, {self.model._meta.label: updated_count}

    async def ahard_delete(self) -> tuple[int, dict[str, int]]:
        """
        Физическое удаление записей из базы данных (навсегда).
        Использует стандартный метод delete() родительского класса.
        """
        return await super().adelete()

    async def arestore(self) -> int:
        """
        Восстановление удаленных записей.

        Returns:
            int: Количество восстановленных записей.
        """
        now = timezone.now()
        return await self.aupdate(deleted_at=None, updated_at=now)


# Создаем класс менеджера через from_queryset
# Позволяет использовать методы SoftDeleteQuerySet напрямую через objects
SoftDeleteManager = models.Manager.from_queryset(SoftDeleteQuerySet)
