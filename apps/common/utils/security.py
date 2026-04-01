"""
Утилиты для криптографии и безопасности.
"""

from secrets import choice
from string import ascii_letters, digits


def generate_temporary_password(length: int = 12) -> str:
    """
    Генерирует надежный временный пароль.

    Args:
        length (int): Длина временного пароля (по умолчанию 12 символов).

    Returns:
        str: Надежный временный пароль.
    """
    alphabet = ascii_letters + digits + "!@#$%^&*"
    temporary_password = "".join(choice(alphabet) for _ in range(length))
    return temporary_password
