"""
Модели для управления клиентами (Юр.лица и ИП).
"""

from typing import TYPE_CHECKING

from django.contrib.postgres.indexes import GinIndex
from django.db import models
from django.utils.translation import gettext_lazy as _
from pghistory import track as pghistory_track

from apps.clients.types import ContactInfo
from apps.common.models import BaseModel
from apps.common.validators import validate_unp
from apps.users.models import Department, User, UserRole

if TYPE_CHECKING:
    from apps.clients.schemas.contacts import ClientContactInfoUpdate


class ClientStatus(models.TextChoices):
    """Статус обслуживания клиента."""

    ACTIVE = "active", "На обслуживании"
    ONBOARDING = "onboarding", "Подключение (Договор)"
    ARCHIVED = "archived", "Архив (Расторгнут)"
    LEAD = "lead", "Потенциальный"


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


@pghistory_track()
class Client(BaseModel):
    """
    Карточка клиента (Контрагента).

    Наследуется от BaseModel.
    Содержит юридическую информацию, настройки налогов и ответственных.
    Использует GIN индексы для быстрого поиска по подстроке (Trigram).
    Использует системное версионирование через pgHistory (триггеры).
    """

    # Основная информация
    name = models.CharField(
        _("Краткое название"),
        max_length=150,
        db_index=True,
        help_text=_("Например: АБВ (для удобного поиска)"),
    )

    full_legal_name = models.CharField(
        _("Полное юридическое название"),
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

    status = models.CharField(
        _("Статус"),
        max_length=20,
        choices=ClientStatus.choices,
        default=ClientStatus.ONBOARDING,
        db_index=True,
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

    primary_accountant = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="clients_primary",
        verbose_name=_("Бухгалтер по первичной документации"),
        help_text=_("Ввод накладных, банка, кассы"),
        limit_choices_to={
            "role__in": [
                UserRole.JUNIOR_ACCOUNTANT,
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
                UserRole.JUNIOR_ACCOUNTANT,
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
        help_text=_("Ответственный за кадровый учет (контракты, ПУ-1, ПУ-2 и т.д.)"),
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

        # Индексы для оптимизации поиска
        indexes = [
            # Комбинированный GIN индекс для быстрого поиска (Trigram)
            # Позволяет делать ILIKE '%запрос%' по любому из трех полей очень быстро
            GinIndex(
                name="client_search_gin_trgm_idx",
                fields=["name", "full_legal_name", "unp"],
                opclasses=["gin_trgm_ops", "gin_trgm_ops", "gin_trgm_ops"],
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} (УНП: {self.unp})"

    @property
    def contact_data(self) -> ContactInfo:
        """
        Превращает JSON из базы в типизированный Pydantic-объект.

        Returns:
            ContactInfo: Объект с данными.
        """

        # Если данных нет или это не словарь, создаем пустую схему
        if not isinstance(self.contact_info, dict) or not self.contact_info:
            return ContactInfo()

        try:
            return ContactInfo.model_validate(self.contact_info)
        except Exception:
            # Модель молча возвращает пустой объект, если данные битые
            # Если будет нужно дебажить битые данные, будет это делать скриптами проверки
            return ContactInfo()

    def set_contact_data(self, data: ContactInfo) -> None:
        """
        Безопасно сохраняет Pydantic-объект в JSON-поле.
        Сохраняет в базу только те поля, которые были реально заполнены.

        Args:
            data (ContactInfo): Новые данные.
        """
        # mode="json" гарантирует, что UUID/Enums станут строками
        # exclude_unset=True: не сохранять дефолты (Field(None))
        # exclude_none=True: не сохранять поля, где явно стоит None
        clean_data = data.model_dump(mode="json", exclude_unset=True, exclude_none=True)
        self.contact_info = clean_data

    def patch_contact_data(self, data: ClientContactInfoUpdate) -> None:
        """
        Частично обновляет JSON-поле contact_info.

        Стратегия слияния:
        1. Берем текущий словарь из БД.
        2. Берем только те поля из data, которые были явно переданы (exclude_unset).
        3. Обновляем (merge) словарь верхнего уровня.
        4. Вложенные списки (contacts) заменяются целиком, если они переданы.

        Args:
            data (ClientContactInfoUpdate): Схема с изменениями.
        """
        # Гарантируем, что работаем со словарем
        current_data = self.contact_info if isinstance(self.contact_info, dict) else {}

        # mode="json" гарантирует, что UUID/Enums станут строками
        # exclude_unset=True: Берем только то, что пришло с фронта
        # exclude_none=False: Разрешаем null, чтобы удалять значения полей
        updates = data.model_dump(exclude_unset=True, mode="json")

        # Нечего обновлять
        if not updates:
            return None

        # Используем распаковку для создания нового словаря
        # Значения из updates перезапишут значения из current_data
        self.contact_info = {**current_data, **updates}

        return None
