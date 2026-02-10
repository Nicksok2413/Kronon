"""
Модели для управления клиентами (Юр.лица и ИП).
"""

from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.common.models import BaseModel
from apps.common.validators import validate_unp
from apps.users.models import Department, User, UserRole


class OrganizationType(models.TextChoices):
    """Типы организаций (РБ)."""

    IP = "ip", "ИП"
    OOO = "ooo", "ООО"
    ODO = "odo", "ОДО"
    OAO = "oao", "ОАО"
    ZAO = "zao", "ЗАО"
    CHUP = "chup", "ЧУП"
    FOND = "fond", "Фонд"
    OTHER = "other", "Другое"


class TaxSystem(models.TextChoices):
    """
    Системы налогообложения (РБ).
    Влияют на график задач и отчетности.
    """

    # Упрощенная система налогообложения
    USN_NO_NDS = "usn_no_nds", "УСН без НДС (6%)"
    USN_NDS = "usn_nds", "УСН с НДС"

    # Общая система налогообложения
    OSN = "osn", "Общая система налогообложения (ОСН)"

    # Для ИП
    IP_EDINY = "ip_ediny", "Единый налог"
    IP_PODOHODNY = "ip_podohodny", "Подоходный налог (ОСН для ИП)"
    NPD = "npd", "Налог на профессиональный доход (НПД)"

    # Особые
    PVT = "pvt", "Парк высоких технологий (ПВТ)"


class ClientStatus(models.TextChoices):
    """Статус обслуживания клиента."""

    ACTIVE = "active", "На обслуживании"
    ONBOARDING = "onboarding", "Подключение (Договор)"
    ARCHIVED = "archived", "Архив (Расторгнут)"
    LEAD = "lead", "Потенциальный"


class Client(BaseModel):
    """
    Карточка клиента (Контрагента).
    Содержит юридическую информацию, настройки налогов и ответственных.
    """

    # Основная информация
    name = models.CharField(
        _("Краткое название"),
        max_length=150,
        db_index=True,
        help_text=_("Например: АБВ (для удобного поиска)"),
    )

    full_legal_name = models.CharField(
        _("Полное юр. название"),
        max_length=255,
        blank=True,
        help_text=_("Например: Общество с ограниченной ответственностью 'АБВ'"),
    )

    # УНП - Учетный номер плательщика (9 цифр для РБ)
    unp = models.CharField(
        _("УНП"),
        max_length=9,
        unique=True,
        db_index=True,
        validators=[validate_unp],
    )

    org_type = models.CharField(
        _("Тип организации"),
        max_length=10,
        choices=OrganizationType.choices,
        default=OrganizationType.OOO,
    )

    # Бухгалтерский контекст
    tax_system = models.CharField(
        _("Система налогообложения"),
        max_length=20,
        choices=TaxSystem.choices,
        default=TaxSystem.USN_NO_NDS,
    )

    status = models.CharField(
        _("Статус"),
        max_length=20,
        choices=ClientStatus.choices,
        default=ClientStatus.ONBOARDING,
        db_index=True,
    )

    # Обслуживающий отдел
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients",
        verbose_name=_("Обслуживающий отдел"),
        help_text=_("Отдел, к которому приписан клиент"),
    )

    # Ответственные
    accountant = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients_accountant",
        verbose_name=_("Ведущий бухгалтер"),
        limit_choices_to={
            "role__in": [
                UserRole.ACCOUNTANT,
                UserRole.LEAD_ACCOUNTANT,
                UserRole.CHIEF_ACCOUNTANT,
            ]
        },
    )

    assistant = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients_assisted",
        verbose_name=_("Бухгалтер по первичной документации"),
        help_text=_("Сотрудник, помогающий с первичкой и рутиной"),
        limit_choices_to={
            "role__in": [
                UserRole.ACCOUNTANT,
                UserRole.LEAD_ACCOUNTANT,
            ]
        },
    )

    payroll_accountant = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients_payroll",
        verbose_name=_("Бухгалтер по заработной плате"),
        help_text=_("Если зарплату считает отдельный специалист"),
        limit_choices_to={
            "role__in": [
                UserRole.ACCOUNTANT,
                UserRole.LEAD_ACCOUNTANT,
            ]
        },
    )

    hr_specialist = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients_hr",
        verbose_name=_("Специалист по кадрам"),
        help_text=_("Ответственный за кадровый учет (ПУ-1, ПУ-2, контракты)"),
        limit_choices_to={"role": UserRole.HR},
    )

    # Контакты (храним JSON, чтобы не плодить таблицы для телефонов/email)
    # Структура: {"director": "Иванов И.И.", "phone": "+375...", "email": "..."}
    contact_info = models.JSONField(
        _("Контактная информация"),
        default=dict,
        blank=True,
    )

    # Интеграции
    google_folder_id = models.CharField(
        _("ID папки Google Drive"),
        max_length=100,
        blank=True,
        help_text=_("ID папки, куда клиенты загружают первичку"),
    )

    class Meta:
        verbose_name = _("Клиент")
        verbose_name_plural = _("Клиенты")
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.name} (УНП: {self.unp})"
