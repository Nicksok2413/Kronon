"""
Схемы для фильтрации списка сотрудников.

Использует возможности Django Ninja (FilterLookup)
для декларативного описания логики фильтрации без написания кастомных методов.
"""

from typing import Annotated
from uuid import UUID

from ninja import Field, FilterLookup, FilterSchema

from apps.users.models import EmploymentStatus, UserRole


class UserFilter(FilterSchema):
    """
    Параметры фильтрации сотрудников.
    Используется как в публичном справочнике, так и в панели внутреннего HR.
    """

    # Выносим логику лукапа во внутреннюю переменную класса для читаемости
    # FilterLookup со списком полей автоматически объединяет их через OR
    # icontains - поиск по подстроке сразу по трем полям без учета регистра
    _search_lookup = FilterLookup(["first_name__icontains", "last_name__icontains", "email__icontains"])

    # Поиск (частичное совпадение)
    search: Annotated[str | None, _search_lookup] = Field(
        default=None,
        description="Поиск (частичное совпадение) по имени, фамилии или email",
    )

    # Фильтры по Enums и связям (FK)
    role: UserRole | None = Field(default=None, description="Фильтр по должности")
    department_id: UUID | None = Field(default=None, description="Фильтр по отделу")
    # Специфичный HR-фильтр (в публичном справочнике он не будет находить ничего секретного, но позволит фильтровать)
    employment_status: EmploymentStatus | None = Field(default=None, description="Статус трудоустройства (Штат/Подряд)")
