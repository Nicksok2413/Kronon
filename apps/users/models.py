"""
Модели пользователей, профилей и оргструктуры.
"""

import uuid

from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.common.utils.paths import RandomFileName
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
    JUNIOR_ACCOUNTANT = "junior", "Младший бухгалтер"
    LAWYER = "lawyer", "Юрисконсульт"
    HR = "hr", "Специалист по кадрам"
    IT_SPECIALIST = "it", "IT-специалист"
    SECURITY_GUARD = "security_guard", "Охранник"


class EmploymentStatus(models.TextChoices):
    """Статус трудоустройства."""

    FULL_TIME = "full_time", "В штате"
    PROBATION = "probation", "Испытательный срок"
    CONTRACTOR = "contractor", "Подряд (договор подряда)"
    PART_TIME = "part_time", "Частичная занятость"


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

    # Переопределяем id
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False, verbose_name="ID")

    # Убираем поле username
    username = None  # type: ignore

    email = models.EmailField(_("Email"), unique=True)

    role = models.CharField(
        _("Роль"),
        max_length=50,
        choices=UserRole.choices,
        default=UserRole.ACCOUNTANT,
    )

    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name=_("Отдел"),
    )

    employment_status = models.CharField(
        _("Статус оформления"),
        max_length=20,
        choices=EmploymentStatus.choices,
        default=EmploymentStatus.PROBATION,  # По умолчанию все новые сотрудники на испытательном сроке
    )

    probation_end_date = models.DateField(
        _("Конец испытательного срока"), null=True, blank=True, help_text=_("Дата окончания испытательного срока")
    )

    # Контрактные данные
    contract_start_date = models.DateField(
        _("Начало контракта"), null=True, blank=True, help_text=_("Дата приема на работу или начала текущего контракта")
    )

    contract_end_date = models.DateField(
        _("Окончание контракта"), null=True, blank=True, help_text=_("Дата истечения срока действия контракта")
    )

    # Отчество (необязательное поле)
    middle_name = models.CharField(_("Отчество"), max_length=150, blank=True)

    # Используем кастомный менеджер
    objects = CustomUserManager()  # type: ignore

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # Email и пароль обязательны по умолчанию

    class Meta:
        verbose_name = _("Сотрудник")
        verbose_name_plural = _("Сотрудники")
        # Сортировка по умолчанию (обратный порядок - новые сверху)
        # UUIDv7 сортируется по времени быстрее, чем created_at
        ordering = ["-id"]

    def __str__(self) -> str:
        return self.email

    @property
    def full_name_rus(self) -> str:
        """Возвращает полное имя в формате: Фамилия Имя Отчество."""
        parts = [self.last_name, self.first_name, self.middle_name]
        return " ".join(filter(None, parts))

    # Метод для проверки испытательного срока
    @property
    def is_on_probation(self) -> bool:
        """Возвращает True если сотрудник на испытательном сроке."""
        if self.employment_status == EmploymentStatus.PROBATION:
            if self.probation_end_date and self.probation_end_date < timezone.now().date():
                return False  # Срок истек, но статус забыли поменять (формально уже не на испытательном)
            return True
        return False


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
