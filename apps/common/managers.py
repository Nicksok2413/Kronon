"""
Менеджер и QuerySet для реализации логики мягкого удаления (Soft Delete).
"""

from typing import Self, TypeVar

from django.db import models
from django.utils import timezone

# Определяем Generic переменную, ограниченную моделями Django
# Это позволяет mypy понимать, с какой именно моделью мы работаем
_M = TypeVar("_M", bound=models.Model)


class SoftDeleteQuerySet(models.QuerySet[_M]):
    """
    Кастомный QuerySet, реализующий логику мягкого удаления.
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

    def delete(self) -> tuple[int, dict[str, int]]:
        """
        Переопределение стандартного метода удаления (Bulk Delete).
        Вместо физического удаления проставляет текущее время в `deleted_at`.

        Returns:
            tuple[int, dict[str, int]]: (Количество удаленных записей, Словарь по типам объектов).
            Формат совпадает со стандартным Django delete().
        """
        # Используем update() для массового обновления
        # Это эффективно (один SQL запрос) и не вызывает сигналы pre_save/post_save
        # (что является стандартным поведением для bulk-операций в Django)
        updated_count = self.update(deleted_at=timezone.now())

        # Эмулируем возвращаемое значение стандартного delete()
        return updated_count, {self.model._meta.label: updated_count}

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        """
        Физическое удаление записей из базы данных (навсегда).
        Использует стандартный метод delete() родительского класса.
        """
        return super().delete()

    def restore(self) -> int:
        """
        Восстановление удаленных записей.

        Returns:
            int: Количество восстановленных записей.
        """
        return self.update(deleted_at=None)


class SoftDeleteManager(models.Manager[_M]):
    """
    Менеджер для моделей с поддержкой мягкого удаления.
    Позволяет использовать методы SoftDeleteQuerySet напрямую через objects.

    Предоставляет удобные прокси-методы для фильтрации, удаления и восстановления записей.
    """

    def get_queryset(self) -> SoftDeleteQuerySet[_M]:
        """
        Возвращает все записи, в том числе "мягко удаленные" (чтобы не ломать админку и каскады).
        """
        return SoftDeleteQuerySet(self.model, using=self._db)

    def active(self) -> SoftDeleteQuerySet[_M]:
        """Прокси для получения активных записей."""
        return self.get_queryset().active()

    def deleted(self) -> SoftDeleteQuerySet[_M]:
        """Прокси для получения удаленных записей."""
        return self.get_queryset().deleted()

    def hard_delete(self) -> tuple[int, dict[str, int]]:
        """Прокси для полного удаления."""
        return self.get_queryset().hard_delete()

    def restore(self) -> int:
        """Прокси для восстановления."""
        return self.get_queryset().restore()
