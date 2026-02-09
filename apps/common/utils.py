"""
Вспомогательные утилиты и функции для всего проекта.
"""

import os
from typing import TYPE_CHECKING
from uuid import uuid4

from django.utils.deconstruct import deconstructible

if TYPE_CHECKING:
    from django.db.models import Model


@deconstructible
class RandomFileName:
    """
    Класс для генерации пути к файлу с рандомизацией имени.
    Позволяет избежать коллизий имен файлов и `predictable resource location` уязвимостей.
    """

    def __init__(self, path_suffix: str):
        """
        Args:
            path_suffix (str): Подпапка внутри MEDIA_ROOT (например, 'users/avatars').
        """
        self.path_suffix = path_suffix

    def __call__(self, instance: Model, filename: str) -> str:
        """
        Args:
            instance ("Model"): Экземпляр модели (Profile, Contract, и т.д.).
            filename (str): Исходное имя файла.

        Returns:
            Сгенерированный путь к файлу.
        """
        # Извлекаем расширение файла
        ext = filename.split(".")[-1].lower()
        # Генерируем UUID имя файла
        filename = f"{uuid4().hex}.{ext}"
        # Возвращаем путь: users/avatars/<uuid>.jpg
        return os.path.join(self.path_suffix, filename)
