"""
Менеджер пользователей для аутентификации по Email.
"""

from typing import TYPE_CHECKING, Any

from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _

from apps.common.managers import SoftDeleteQuerySet

if TYPE_CHECKING:
    from apps.users.models import User


# Наследуем класс менеджера от BaseUserManager через from_queryset
# Позволяет использовать методы SoftDeleteQuerySet напрямую через objects
class CustomUserManager(BaseUserManager["User"].from_queryset(SoftDeleteQuerySet)):  # type: ignore[misc]
    """
    Кастомный менеджер модели пользователя.

    Использует email в качестве уникального идентификатора для аутентификации (Email-auth)
    вместо стандартного имени пользователя (username).
    Наследует логику мягкого удаления и OLP-фильтрацию.
    """

    # TODO: подумать над async
    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> User:
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
        user: User = self.model(email=email, **extra_fields)

        # Хэшируем пароль
        user.set_password(password)

        # Сохраняем, используя базу данных, к которой привязан менеджер
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str | None = None, **extra_fields: Any) -> User:
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
        extra_fields.setdefault("role", "sys_admin")

        # TODO: подумать нужны ли эти проверки
        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Суперпользователь должен иметь is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Суперпользователь должен иметь is_superuser=True."))

        return self.create_user(email, password, **extra_fields)
