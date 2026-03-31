"""
Настройки админ-панели для пользователей и структуры.
"""

from typing import Any

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.http import HttpRequest
from django.utils import timezone
from django.utils.html import format_html
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _

from apps.common.admin import KrononBaseAdmin
from apps.users.constants import SYSTEM_USER_ID
from apps.users.models import Department, EmploymentStatus, Profile, User


class ProfileInline(admin.StackedInline[Profile, User]):
    """Встроенное редактирование профиля внутри формы пользователя."""

    model = Profile
    can_delete = False
    verbose_name_plural = _("Профиль")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin[Department]):
    """Админка для отделов."""

    list_display = ("name", "head", "parent", "get_employees_count")
    search_fields = ("name", "head__email", "head__last_name")
    list_select_related = ("head", "parent")  # Оптимизация запросов

    @admin.display(description=_("Сотрудников"))
    def get_employees_count(self, obj: Department) -> int:
        return obj.employees.count()


@admin.register(User)
class UserAdmin(KrononBaseAdmin[User], DjangoUserAdmin[User]):
    """
    Кастомная админка пользователя.

    Наследует:
    KrononBaseAdmin: аудит (pghistory), Trace ID, Soft/Hard Delete кнопки.
    DjangoUserAdmin: стандартные fieldsets, смену пароля и права доступа.

    Добавляет фильтры, поиск и inline-редактирование профиля.
    """

    list_display = (
        "email",
        "soft_delete_status",
        "is_staff_status",
        "last_name",
        "first_name",
        "role",
        "department",
        "probation_badge",
        "contract_status_badge",
    )

    # Явно указываем поиск по email (вместо username)
    search_fields = ("email", "last_name", "first_name")

    # Сортировка по email для удобства
    ordering = ("email",)

    # Оптимизация запросов (чтобы не делать N+1 запрос в списке)
    list_select_related = ("department",)

    # Добавляем профиль вниз формы
    inlines = (ProfileInline,)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Персональные данные"), {"fields": ("last_name", "first_name", "middle_name")}),
        (
            _("Компания"),
            {
                "fields": (
                    "role",
                    "department",
                    "employment_status",
                    "probation_end_date",
                    # Группируем даты контракта
                    ("contract_start_date", "contract_end_date"),
                )
            },
        ),
        (_("Права доступа"), {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        (_("Важные даты"), {"fields": ("last_login", "date_joined")}),
    )

    # Поля для формы создания
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "password", "confirm_password"),
            },
        ),
    )

    # Кастомный SoftDeleteFilter фильтр + базовые фильтры
    def get_list_filter(self, request: HttpRequest) -> list[Any]:
        """Расширяет фильтрацию списка."""

        soft_delete_filter = list(super().get_list_filter(request))

        filters = [
            "employment_status",
            "role",
            "department",
        ]

        return soft_delete_filter + filters

    # --- Делаем системного юзера неизменяемым (Read-only) ---

    def has_change_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        """Запрещаем редактировать системного пользователя."""
        if obj and str(obj.id) == str(SYSTEM_USER_ID):
            return False

        return super().has_change_permission(request, obj)

    def has_delete_permission(self, request: HttpRequest, obj: Any | None = None) -> bool:
        """Запрещаем удалять системного пользователя."""
        if obj and str(obj.id) == str(SYSTEM_USER_ID):
            return False

        return super().has_delete_permission(request, obj)

    # --- UI helpers ---

    @classmethod
    def _render_badge(cls, text: str, color_style: str) -> SafeString:
        """Универсальный отрисовщик бейджей."""
        base_style = "padding: 3px 6px; border-radius: 4px; font-weight: bold; white-space: nowrap;"

        return format_html('<span style="{} {}">{}</span>', base_style, color_style, text)

    @admin.display(description=_("Staff"))
    def is_staff_status(self, obj: User) -> str:
        """"""
        return "✔" if obj.is_staff else "—"

    @admin.display(description=_("Испытательный срок"), ordering="probation_end_date")
    def probation_badge(self, obj: User) -> str:
        """
        Рисует HTML бейдж в списке пользователей.

        Показывает дату окончания испытательного срока или индикатор договора подряда:
        Красный - дата окончания испытательного срока.
        Желтый - сотрудник на договоре подряда.
        """
        if obj.employment_status == EmploymentStatus.PROBATION:
            date_str = obj.probation_end_date.strftime("%d.%m.%Y") if obj.probation_end_date else "???"
            # Красный бейдж (дата окончания испытательного срока)
            return self._render_badge(text=f"{date_str}", color_style="color: #cc0000; background-color: #ffcccc;")

        elif obj.employment_status == EmploymentStatus.CONTRACTOR:
            # Желтый бейдж (договор подряда)
            return self._render_badge(text=str(_("Подряд")), color_style="color: #999900; background-color: #ffffcc;")
        else:
            return ""

    @admin.display(description=_("Контракт"), ordering="contract_end_date")
    def contract_status_badge(self, obj: User) -> str:
        """
        Рисует HTML бейдж в списке пользователей.

        Показывает дату окончания контракта:
        Черный - контракт истек.
        Красный - истекает < 30 дней.
        Оранжевый - истекает < 60 дней.
        Зеленый - ок.
        """
        if not obj.contract_end_date:
            return "—"

        today = timezone.now().date()
        days_left = (obj.contract_end_date - today).days
        date_str = obj.contract_end_date.strftime("%d.%m.%Y")

        if days_left < 0:
            # Черный бейдж (истек)
            return self._render_badge(color_style="background-color: #333; color: #fff;", text=f"ИСТЕК ({date_str})")
        elif days_left < 30:
            # Красный бейдж (осталось меньше 30 дней)
            return self._render_badge(
                color_style="background-color: #ffcccc; color: #cc0000;", text=f"< 30 дн ({date_str})"
            )
        elif days_left < 60:
            # Оранжевый бейдж (осталось меньше 60 дней)
            return self._render_badge(
                color_style="background-color: #fff4e5; color: #663c00;", text=f"< 60 дн ({date_str})"
            )
        else:
            # Зеленый бейдж (осталось больше 60 дней)
            return self._render_badge(text=date_str, color_style="background-color: #e6ffed; color: #22863a;")
