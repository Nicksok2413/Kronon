"""
Настройки админ-панели для пользователей и структуры.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

from apps.users.models import Department, Profile, User


class ProfileInline(admin.StackedInline):
    """Встроенное редактирование профиля внутри формы пользователя."""

    model = Profile
    can_delete = False
    verbose_name_plural = _("Профиль")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Админка для отделов."""

    list_display = ("name", "head", "parent", "get_employees_count")
    search_fields = ("name", "head__email", "head__last_name")
    list_select_related = ("head", "parent")  # Оптимизация запросов

    @admin.display(description=_("Сотрудников"))
    def get_employees_count(self, obj: Department) -> int:
        return obj.employees.count()


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """
    Кастомная админка пользователя.
    Добавляет фильтры, поиск и inline-редактирование профиля.
    """

    ordering = ["email"]
    list_display = ("email", "last_name", "first_name", "role", "department", "is_active")
    list_filter = ("role", "department", "is_active", "is_staff")
    search_fields = ("email", "last_name", "first_name")

    # Добавляем профиль вниз формы
    inlines = (ProfileInline,)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        (_("Персональные данные"), {"fields": ("last_name", "first_name", "middle_name")}),
        (_("Компания"), {"fields": ("role", "department")}),
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
