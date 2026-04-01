"""
Модели пользователей, профилей и оргструктуры.
"""

import uuid
from typing import Any

from django.contrib.auth.models import AbstractUser
from django.core.validators import FileExtensionValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from pghistory import DeleteEvent, InsertEvent, UpdateEvent
from pghistory import track as pghistory_track
from pgtrigger.contrib import Protect
from pgtrigger.core import Delete, Q, Update

from apps.common.models import BaseModel, TimeStampedModel
from apps.common.utils.paths import RandomFileName
from apps.common.validators import validate_image_size, validate_international_phone_number
from apps.users.constants import SYSTEM_USER_ID
from apps.users.managers import CustomUserManager

# ==============================================================================
# Department, User & Profile
# ==============================================================================


class UserRole(models.TextChoices):
    """
    Роли сотрудников в системе Kronon.
    Влияют на права доступа и бизнес-логику.
    """

    DIRECTOR = "director", "Директор"
    SYSTEM_ADMINISTRATOR = "sys_admin", "Системный администратор"
    CHIEF_ACCOUNTANT = "chief_acc", "Главный бухгалтер"
    LEAD_ACCOUNTANT = "lead_acc", "Ведущий бухгалтер"
    ACCOUNTANT = "accountant", "Бухгалтер"
    JUNIOR_ACCOUNTANT = "junior", "Младший бухгалтер"
    LAWYER = "lawyer", "Юрисконсульт"
    HR = "hr", "Специалист по кадрам (аутсорс)"
    INTERNAL_HR = "internal_hr", "Внутренний HR"
    IT_SPECIALIST = "it", "IT-специалист"
    SECURITY_GUARD = "security_guard", "Охранник"


class EmploymentStatus(models.TextChoices):
    """Статус трудоустройства."""

    FULL_TIME = "full_time", "В штате"
    PROBATION = "probation", "Испытательный срок"
    CONTRACTOR = "contractor", "Подряд (договор подряда)"
    PART_TIME = "part_time", "Частичная занятость"


class Department(BaseModel):
    """
    Организационная единица (Отдел).

    Наследуется от BaseModel.
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


@pghistory_track(
    InsertEvent(),
    UpdateEvent(),
    DeleteEvent(),
    exclude=["last_login"],
    meta={
        "indexes": [
            # Функциональный B-tree индекс для correlation_id
            models.Index(
                models.F("pgh_context__correlation_id"),
                name="user_pgh_corr_idx",
            ),
        ],
    },
)
class User(AbstractUser, TimeStampedModel):
    """
    Кастомная модель пользователя Kronon.

    Наследует стандартные поля Django Auth от AbstractUser и таймстэмпы, имеет логику мягкого удаления (Soft Delete).
    Использует email вместо username и UUIDv7 в качестве первичного ключа (сортируемый).

    Содержит данные авторизации, роль, отдел и контрактные данные.
    Личные данные вынесены в модель Profile.
    """

    # Переопределяем id
    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False, verbose_name="ID")

    # Поле мягкого удаления
    deleted_at = models.DateTimeField(
        _("Дата удаления"),
        null=True,
        blank=True,
        editable=False,
    )

    # Убираем поле username
    username = None  # type: ignore

    email = models.EmailField(_("Email"), unique=True)

    # Отчество (необязательное поле)
    middle_name = models.CharField(_("Отчество"), max_length=150, blank=True)

    role = models.CharField(
        _("Должность"),
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

    # Контрактные данные
    probation_end_date = models.DateField(
        _("Конец испытательного срока"), null=True, blank=True, help_text=_("Дата окончания испытательного срока")
    )

    contract_start_date = models.DateField(
        _("Начало контракта"), null=True, blank=True, help_text=_("Дата приема на работу или начала текущего контракта")
    )

    contract_end_date = models.DateField(
        _("Окончание контракта"), null=True, blank=True, help_text=_("Дата истечения срока действия контракта")
    )

    # Используем кастомный менеджер
    objects = CustomUserManager()  # type: ignore

    # Стандартный менеджер для чистого поведения
    all_objects = models.Manager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []  # Email и пароль обязательны по умолчанию

    class Meta:
        verbose_name = _("Сотрудник")
        verbose_name_plural = _("Сотрудники")
        # Сортировка по умолчанию (обратный порядок - новые сверху)
        # UUIDv7 сортируется по времени быстрее, чем created_at
        ordering = ["-id"]

        # Защищаем системного юзера от изменения/удаления на уровне БД
        triggers = [
            Protect(name="protect_system_user", operation=(Update | Delete), condition=Q(old__id=SYSTEM_USER_ID))
        ]

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

    # --- Для админки ---

    @property
    def is_deleted(self) -> bool:
        """Удобное свойство для проверки статуса."""
        return self.deleted_at is not None

    def delete(self, using: Any = None, keep_parents: bool = False) -> tuple[int, dict[str, int]]:
        """Синхронное мягкое удаление пользователя (Soft Delete)."""
        self.deleted_at = timezone.now()

        # Деактивируем (чтобы мягко удалённый юзер не мог залогиниться)
        self.is_active = False

        # Используем update_fields для оптимизации SQL запроса
        self.save(update_fields=["deleted_at", "is_active", "updated_at"])
        return 1, {self._meta.label: 1}

    async def adelete(self, using: Any = None, keep_parents: bool = False) -> tuple[int, dict[str, int]]:
        """Асинхронное мягкое удаление пользователя (Soft Delete)."""
        self.deleted_at = timezone.now()

        # Деактивируем (чтобы мягко удалённый юзер не мог залогиниться)
        self.is_active = False

        # Используем update_fields для оптимизации SQL запроса
        await self.asave(using=using, update_fields=["deleted_at", "is_active", "updated_at"])
        return 1, {self._meta.label: 1}

    def restore(self) -> None:
        """Синхронное восстановление удаленного пользователя."""
        self.deleted_at = None

        # Активируем
        self.is_active = True

        # Используем update_fields для оптимизации SQL запроса
        self.save(update_fields=["deleted_at", "is_active", "updated_at"])

    async def arestore(self) -> None:
        """Асинхронное восстановление удаленного пользователя."""
        self.deleted_at = None

        # Активируем
        self.is_active = True

        # Используем update_fields для оптимизации SQL запроса
        await self.asave(update_fields=["deleted_at", "is_active", "updated_at"])

    def hard_delete(self, using: Any = None, keep_parents: bool = False) -> tuple[int, dict[str, int]]:
        """Синхронное физическое удаление пользователя из БД (Hard Delete)."""
        return super().delete(using=using, keep_parents=keep_parents)

    async def ahard_delete(self, using: Any = None, keep_parents: bool = False) -> tuple[int, dict[str, int]]:
        """Асинхронное физическое удаление пользователя из БД (Hard Delete)."""
        return await super().adelete(using=using, keep_parents=keep_parents)


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

    allowed_sick_days = models.PositiveSmallIntegerField(
        _("Доступно дней здоровья в год"),
        default=3,
        help_text=_("Количество оплачиваемых отгулов по болезни без справки"),
    )

    class Meta:
        verbose_name = _("Профиль")
        verbose_name_plural = _("Профили")

    def __str__(self) -> str:
        return f"Профиль {self.user.email}"


# ==============================================================================
# Absence (отсутствие сотрудника)
# ==============================================================================


class AbsenceType(models.TextChoices):
    """
    Типы отсутствий сотрудника на рабочем месте.
    """

    VACATION = "vacation", "Трудовой отпуск"
    SICK_LEAVE = "sick_leave", "Больничный (официальный)"
    SICK_DAY = "sick_day", "День здоровья (без справки)"
    UNPAID = "unpaid", "Отпуск за свой счет"
    MATERNITY = "maternity", "Декретный отпуск"
    BUSINESS_TRIP = "business_trip", "Командировка"


class AbsenceStatus(models.TextChoices):
    """
    Статусы согласования отсутствия.
    """

    PLANNED = "planned", "Запланирован"
    PENDING = "pending", "На согласовании"
    APPROVED = "approved", "Утвержден"
    REJECTED = "rejected", "Отклонен"
    COMPLETED = "completed", "Завершен"
    CANCELLED = "cancelled", "Отменен"


class Absence(BaseModel):
    """
    Запись об отсутствии сотрудника (отпуск, больничный и т.д.).

    Наследуется от BaseModel (UUIDv7, SoftDelete).
    Используется для учета рабочего времени и передачи дел.

    Attrs:
        user (User): Сотрудник, который будет отсутствовать.
        absence_type (AbsenceType): Тип отсутствия.
        status (AbsenceStatus): Текущий статус согласования.
        start_date (date): Дата начала.
        end_date (date): Дата окончания.
        reason (str): Примечание или причина.
        approved_by (User): Кто согласовал (если статус APPROVED).
    """

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="absences",
        verbose_name=_("Сотрудник"),
    )

    absence_type = models.CharField(
        _("Тип отсутствия"),
        max_length=20,
        choices=AbsenceType.choices,
    )

    status = models.CharField(
        _("Статус"),
        max_length=20,
        choices=AbsenceStatus.choices,
        default=AbsenceStatus.PLANNED,
        db_index=True,
    )

    start_date = models.DateField(_("Дата начала"), db_index=True)

    # Дата окончания опциональна (если отпуск - дата обязательна, если больничный - может быть null)
    end_date = models.DateField(
        _("Дата окончания"),
        blank=True,
        null=True,
        db_index=True,
        help_text=_("Оставьте пустым для открытого больничного"),
    )

    reason = models.TextField(
        _("Причина / Примечание"),
        blank=True,
        null=True,
        help_text=_("Дополнительная информация (например, номер больничного листа)"),
    )

    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="approved_absences",
        verbose_name=_("Согласующий"),
        help_text=_("Кто утвердил отсутствие (HR или Директор)"),
    )

    class Meta:
        verbose_name = _("Отсутствие")
        verbose_name_plural = _("Отсутствия")
        # Сортировка по умолчанию: по началу события (для календаря)
        ordering = ["-start_date"]

    def __str__(self) -> str:
        end = self.end_date if self.end_date else "По н.в."
        return f"{self.user.email} ({self.get_absence_type_display()}): {self.start_date} - {end}"
