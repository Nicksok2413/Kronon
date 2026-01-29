"""
Менеджер пользователей для аутентификации по Email.
"""
from typing import Any

from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _


class CustomUserManager(BaseUserManager):
    """
    Кастомный менеджер модели пользователя.

    Использует email в качестве уникального идентификатора для аутентификации
    вместо стандартного имени пользователя (username).
    """

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> Any:
        """
        Создает и сохраняет пользователя с указанным email и паролем.

        Args:
            email (str): Email пользователя (обязательный).
            password (str | None): Пароль пользователя.
            **extra_fields: Дополнительные поля для модели User.

        Returns:
            User: Созданный экземпляр пользователя.

        Raises:
            ValueError: Если email не указан.
        """
        if not email:
            raise ValueError(_("Email должен быть указан."))

        # Приводим email к стандартному виду (lowercase доменной части)
        email = self.normalize_email(email)

        # Создаем модель, используя текущий класс (self.model)
        user = self.model(email=email, **extra_fields)

        # Хешируем пароль
        user.set_password(password)

        # Сохраняем, используя базу данных, к которой привязан менеджер
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any) -> Any:
        """
        Создает и сохраняет суперпользователя (администратора).

        Автоматически устанавливает флаги is_staff=True и is_superuser=True.

        Args:
            email (str): Email суперпользователя.
            password (str | None): Пароль суперпользователя.
            **extra_fields: Дополнительные поля.

        Returns:
            User: Созданный экземпляр суперпользователя.

        Raises:
            ValueError: Если is_staff или is_superuser не установлены в True.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Суперпользователь должен иметь is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Суперпользователь должен иметь is_superuser=True."))

        return self.create_user(email, password, **extra_fields)
