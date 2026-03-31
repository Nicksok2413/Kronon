"""
Приватные схемы данных (DTO) для HR-отдела и руководства.
Содержат чувствительные данные (контракты, статусы, испытательные сроки).
"""

from datetime import date

from ninja import Field

from apps.users.models import EmploymentStatus
from apps.users.schemas.directory import UserDirectoryOut


class EmployeePrivateOut(UserDirectoryOut):
    """
    Схема сотрудника с полными кадровыми данными.
    Наследует базовые поля из UserDirectoryOut.
    Доступна только внутреннему HR и администрации.
    """

    employment_status: EmploymentStatus = Field(..., description="Статус трудоустройства")
    contract_start_date: date | None = Field(default=None, description="Дата начала контракта")
    contract_end_date: date | None = Field(default=None, description="Дата окончания контракта")
    probation_end_date: date | None = Field(default=None, description="Дата окончания испытательного срока")

    # Вычисляемое поле из модели (computed property)
    # Ninja/Pydantic умеет вызывать методы модели, если имя совпадает
    is_on_probation: bool = Field(..., description="Флаг: находится ли на испытательном сроке")

    is_active: bool = Field(..., description="Активен ли аккаунт (не уволен)")
