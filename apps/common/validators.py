"""
Кастомные валидаторы для всего проекта.
"""

from typing import Any

import phonenumbers
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files import File
from django.core.validators import RegexValidator
from django.utils.deconstruct import deconstructible
from django.utils.translation import gettext_lazy as _


@deconstructible
class FileSizeValidator:
    """
    Валидатор для проверки максимального размера файла.
    """

    def __init__(self, max_size_mb: int, message: str | None = None) -> None:
        """
        Args:
            max_size_mb (int): Максимальный размер файла в мегабайтах.
            message (str | None): Кастомное сообщение об ошибке.
        """
        self.max_size_mb = max_size_mb
        self.message = message or _("Размер файла не должен превышать {max_size} МБ.").format(max_size=max_size_mb)

    def __call__(self, file: File[Any]) -> None:
        """
        Args:
            file (File): Загружаемый файл.
        """
        if file.size > self.max_size_mb * 1024 * 1024:
            raise ValidationError(self.message)

    def __eq__(self, other: Any) -> bool:
        """
        Необходимо для сравнения объектов валидатора при создании миграций.
        """
        return isinstance(other, self.__class__) and self.max_size_mb == other.max_size_mb


def validate_international_phone_number(value: str) -> None:
    """
    Валидирует телефонный номер с помощью библиотеки phonenumbers.
    Поддерживает международные форматы и локальный формат региона DEFAULT_PHONE_REGION.
    """
    if not value:
        return

    try:
        # Пытаемся распарсить номер
        parsed_phone = phonenumbers.parse(value, settings.DEFAULT_PHONE_REGION)

        # Проверяем, является ли номер валидным
        if not phonenumbers.is_valid_number(parsed_phone):
            raise ValidationError(_("Введен некорректный телефонный номер. Пример: +375291234567"))

    except phonenumbers.NumberParseException:
        # Если библиотека не смогла распарсить номер, он невалиден
        raise ValidationError(_("Номер телефона содержит недопустимые символы.")) from None


# Инстансы валидаторов для повторного использования
validate_image_size = FileSizeValidator(max_size_mb=settings.MAX_IMAGE_SIZE_MB)
validate_document_size = FileSizeValidator(max_size_mb=settings.MAX_DOCUMENT_SIZE_MB)

# Валидатор для полей, где должны быть только буквы и дефис (ФИО)
validate_alpha_hyphen = RegexValidator(
    r"^[а-яА-ЯёЁa-zA-Z\s-]+$", message=_("Допустимы только буквы, пробелы и дефисы.")
)
