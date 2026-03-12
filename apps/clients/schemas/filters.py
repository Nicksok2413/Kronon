"""
Схемы для фильтрации списка клиентов.

Использует современные возможности Django Ninja (FilterLookup)
для декларативного описания логики фильтрации без написания кастомных методов.
"""

from typing import Annotated
from uuid import UUID

from ninja import Field, FilterLookup, FilterSchema

from apps.clients.models import ClientStatus, OrganizationType, TaxSystem


class ClientFilter(FilterSchema):
    """
    Параметры фильтрации клиентов.
    """

    # Выносим логику лукапа во внутреннюю переменную класса для читаемости
    # FilterLookup со списком полей автоматически объединяет их через OR
    # icontains - поиск по подстроке без учета регистра
    _search_lookup = FilterLookup(["name__icontains", "full_legal_name__icontains", "unp__icontains"])

    # Поиск (частичное совпадение)
    search: Annotated[str | None, _search_lookup] = Field(
        default=None, description="Поиск (частичное совпадение) по названию, полному названию или УНП"
    )

    # Фильтры по Enums
    status: ClientStatus | None = Field(default=None, description="Статус обслуживания")
    org_type: OrganizationType | None = Field(default=None, description="Тип организации")
    tax_system: TaxSystem | None = Field(default=None, description="Система налогообложения")

    # Фильтры по FK
    department_id: UUID | None = Field(default=None, description="Фильтр по обслуживающему отделу")
    accountant_id: UUID | None = Field(default=None, description="Фильтр по ведущему бухгалтеру")
    primary_accountant_id: UUID | None = Field(default=None, description="Фильтр по бухгалтеру первичной документации")
    payroll_accountant_id: UUID | None = Field(default=None, description="Фильтр по бухгалтеру по заработной плате")
    hr_specialist_id: UUID | None = Field(default=None, description="Фильтр по специалисту по кадрам")
