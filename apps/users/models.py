"""
Модели пользователей, профилей и оргструктуры.
"""

from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.utils import RandomFileName
from apps.common.validators import validate_image_size, validate_international_phone_number
from apps.users.managers import CustomUserManager


class UserRole(models.TextChoices):
    """
    Роли сотрудников в системе Kronon.
    Влияют на права доступа и бизнес-логику.
    """

    DIRECTOR = "director", "Директор"
    CHIEF_ACCOUNTANT = "chief_acc", "Главный бухгалтер"
    LEAD_ACCOUNTANT = "lead_acc", "Ведущий бухгалтер"
    ACCOUNTANT = "accountant", "Бухгалтер"
    LAWYER = "lawyer", "Юрисконсульт"
    HR = "hr", "Специалист по кадрам"
    INTERN = "intern", "Стажер"
    IT_SPECIALIST = "it", "IT-специалист"


class Department(models.Model):
    """
    Организационная единица (Отдел).
    Может иметь начальника и родительский отдел.
    """

    name = models.CharField(_("Название"), max_length=150, unique=True)

    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sub_departments",
        verbose_name=_("Родительский отдел"),
    )

    # Используем строку 'User', так как класс User определен ниже
    head = models.ForeignKey(
        "User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="headed_department",
        verbose_name=_("Начальник отдела"),
    )

    class Meta:
        verbose_name = _("Отдел")
        verbose_name_plural = _("Отделы")
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class User(AbstractUser):
    """
    Кастомная модель пользователя Kronon.
    Использует email вместо username. Содержит только данные авторизации и позицию.
    Личные данные вынесены в модель Profile.
    """

    # Убираем поле username
    username = None  # type: ignore

    email = models.EmailField(_("Email"), unique=True)

    role = models.CharField(
        _("Роль"),
        max_length=50,
        choices=UserRole.choices,
        default=UserRole.ACCOUNTANT,
    )

    # Отчество (необязательное поле)
    middle_name = models.CharField(_("Отчество"), max_length=150, blank=True)

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name=_("Отдел"),
    )

    # Используем кастомный менеджер
    objects = CustomUserManager()  # type: ignore

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # Email и пароль обязательны по умолчанию

    class Meta:
        verbose_name = _("Сотрудник")
        verbose_name_plural = _("Сотрудники")

    def __str__(self) -> str:
        return self.email

    @property
    def full_name_rus(self) -> str:
        """Возвращает полное имя в формате: Фамилия Имя Отчество."""
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(filter(None, parts))


class Profile(models.Model):
    """
    Расширенный профиль сотрудника.
    Хранит фото, телефон, дату рождения и биографию.
    """

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        primary_key=True,
        related_name="profile",
        verbose_name=_("Сотрудник"),
    )

    photo = models.ImageField(
        _("Фото"),
        upload_to=RandomFileName("users/avatars"),
        null=True,
        blank=True,
        validators=[
            FileExtensionValidator(allowed_extensions=["jpg", "jpeg", "png"]),
            validate_image_size,
        ],
    )

    phone = models.CharField(
        _("Телефон"),
        max_length=30,
        blank=True,
        validators=[validate_international_phone_number],
    )

    birth_date = models.DateField(_("Дата рождения"), null=True, blank=True)
    bio = models.TextField(_("О себе"), blank=True, help_text=_("Краткая информация, навыки, хобби"))

    class Meta:
        verbose_name = _("Профиль")
        verbose_name_plural = _("Профили")

    def __str__(self) -> str:
        return f"Профиль {self.user.email}"
