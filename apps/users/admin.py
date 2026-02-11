"""
Настройки админ-панели для пользователей и структуры.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _

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
class UserAdmin(BaseUserAdmin[User]):
    """
    Кастомная админка пользователя.
    Добавляет фильтры, поиск и inline-редактирование профиля.
    """

    ordering = ["email"]
    list_display = (
        "email",
        "last_name",
        "first_name",
        "role",
        "department",
        "probation_badge",
        "contract_status_badge",
        "is_active",
    )

    list_filter = (
        "role",
        "department",
        "employment_status",
        "is_active",
        "is_staff",
    )

    search_fields = ("email", "last_name", "first_name")

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

    @classmethod
    def _render_badge(cls, text: str, color_style: str) -> str:
        """Универсальный отрисовщик бейджей."""
        base_style = "padding: 3px 6px; border-radius: 4px; font-weight: bold; white-space: nowrap;"

        return format_html('<span style="{} {}">{}</span>', base_style, color_style, text)

    @admin.display(description=_("Статус"), ordering="probation_end_date")
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
            return self._render_badge(text=f"IS ({date_str})", color_style="color: #cc0000; background-color: #ffcccc;")

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
