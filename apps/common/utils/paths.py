"""
Утилиты для работы с файловыми путями и именами.
"""

import os
import uuid
from typing import TYPE_CHECKING

from django.utils.deconstruct import deconstructible

if TYPE_CHECKING:
    from django.db.models import Model


@deconstructible
class RandomFileName:
    """
    Генератор пути к файлу с использованием UUIDv7 для уникальности и хронологической сортировки.

    Позволяет избежать коллизий имен и делает предсказуемым порядок файлов в хранилище.
    Класс декорирован @deconstructible для корректной сериализации в миграциях Django.
    """

    def __init__(self, path_suffix: str) -> None:
        """
        Инициализация генератора.

        Args:
            path_suffix (str): Подпапка внутри MEDIA_ROOT (например, 'users/avatars').
        """
        self.path_suffix = path_suffix

    def __call__(self, instance: Model, filename: str) -> str:
        """
        Генерирует новый путь сохранения файла.

        Args:
            instance (Model): Экземпляр модели, к которой привязан файл.
            filename (str): Оригинальное имя загружаемого файла.

        Returns:
            str: Относительный путь для сохранения (например, 'users/avatars/018d...f2.jpg').
        """
        # Извлекаем расширение файла (если расширения нет, ext будет пустым)
        ext = ""

        if "." in filename:
            ext = filename.rsplit(".", 1)[-1].lower()
            ext = f".{ext}"

        # Генерируем UUIDv7 (сортируемый по времени уникальный ID)
        new_filename = f"{uuid.uuid7().hex}{ext}"

        # Собираем итоговый путь
        return os.path.join(self.path_suffix, new_filename)

    def __eq__(self, other: object) -> bool:
        """
        Необходимо для корректного сравнения при создании миграций.
        """
        return isinstance(other, RandomFileName) and self.path_suffix == other.path_suffix
