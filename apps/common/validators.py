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


def validate_international_phone_number(phone: str) -> None:
    """
    Валидирует телефонный номер с помощью библиотеки phonenumbers.
    Поддерживает международные форматы и локальный формат региона DEFAULT_PHONE_REGION.
    """
    # Если телефон не указан, пропускаем валидацию
    if not phone:
        return None

    try:
        # Пытаемся распарсить номер
        parsed_phone = phonenumbers.parse(phone, settings.DEFAULT_PHONE_REGION)

        # Проверяем, является ли номер валидным
        if not phonenumbers.is_valid_number(parsed_phone):
            raise ValidationError(_("Введен некорректный телефонный номер. Пример: +375291234567"))

    except phonenumbers.NumberParseException:
        # Если библиотека не смогла распарсить номер, он невалиден
        raise ValidationError(_("Номер телефона содержит недопустимые символы")) from None


def validate_phone_pydantic(phone: str | None) -> str | None:
    """
    Валидатор телефона для использования в Pydantic схемах (Django Ninja).
    Преобразует Django ValidationError в Pydantic ValueError.
    """
    # Если телефон не указан, пропускаем валидацию
    if not phone:
        return None

    # Используем validate_international_phone_number
    # Перехватываем Django ValidationError и кидаем ValueError
    try:
        validate_international_phone_number(phone)
    except ValidationError as exc:
        # Pydantic ожидает ValueError для ошибок валидации
        raise ValueError(exc.message) from exc
    return phone


def validate_unp(unp: str) -> None:
    """
    Валидирует УНП (Учетный номер плательщика, Беларусь).
    Алгоритм проверки контрольной суммы для ИП и юридических лиц.
    """
    if not unp.isdigit() or len(unp) != 9:
        raise ValidationError(_("УНП должен состоять из 9 цифр"))

    # Алгоритм проверки контрольной суммы для ИП и Юр.лиц
    # (Для ИП алгоритм такой же, коэффициенты те же)
    digits = [int(digit) for digit in unp]
    weights = [29, 23, 19, 17, 13, 7, 5, 3]

    checksum = sum(digit * weight for digit, weight in zip(digits[:8], weights, strict=True))
    remainder = checksum % 11

    # Если остаток 10, повторяем расчет с другим набором весов (редкий случай)
    # Но для большинства УНП достаточно базовой проверки
    # В упрощенном варианте, если остаток 10 - УНП невалиден (обычно такие не выдают)
    if remainder == 10:
        raise ValidationError(_("Некорректный формат УНП (ошибка контрольной суммы)"))

    calculated_control_digit = remainder

    if calculated_control_digit != digits[8]:
        raise ValidationError(_("Недействительный УНП (не совпадает контрольная сумма)"))


# Инстансы валидаторов для повторного использования
validate_image_size = FileSizeValidator(max_size_mb=settings.MAX_IMAGE_SIZE_MB)
validate_document_size = FileSizeValidator(max_size_mb=settings.MAX_DOCUMENT_SIZE_MB)

# Валидатор для полей, где должны быть только буквы и дефис (ФИО)
validate_alpha_hyphen = RegexValidator(r"^[а-яА-ЯёЁa-zA-Z\s-]+$", message=_("Допустимы только буквы, пробелы и дефисы"))
