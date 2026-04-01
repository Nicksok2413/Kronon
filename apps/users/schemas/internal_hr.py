"""
Приватные схемы данных (DTO) для внутреннего HR и руководства.
Содержат чувствительные данные (контракты, статусы, испытательные сроки).
"""

from datetime import date, datetime
from uuid import UUID

from ninja import Field, Schema
from pydantic import ConfigDict, EmailStr

from apps.users.models import EmploymentStatus, UserRole
from apps.users.schemas.directory import UserDirectoryOut


class EmployeePrivateOut(UserDirectoryOut):
    """
    Схема сотрудника с полными кадровыми данными (ответ API).
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

    created_at: datetime = Field(..., description="Дата и время создания сотрудника")
    updated_at: datetime = Field(..., description="Дата и время последнего изменения сотрудника")


class HireResponseOut(Schema):
    """
    Схема ответа при найме сотрудника (содержит временный пароль).
    """

    employee: EmployeePrivateOut
    temporary_password: str = Field(..., description="Сгенерированный временный пароль для входа")


class EmployeeCreate(Schema):
    """
    Схема для найма нового сотрудника (входные данные).
    """

    model_config = ConfigDict(
        extra="forbid",  # Запрет лишних полей (защита от опечаток фронта)
        str_strip_whitespace=True,  # Автоматически убирать лишние пробелы в начале/конце строк
    )

    email: EmailStr = Field(..., description="Рабочий email (логин)")
    first_name: str = Field(..., min_length=2, max_length=150, description="Имя")
    last_name: str = Field(..., min_length=2, max_length=150, description="Фамилия")
    middle_name: str | None = Field(default=None, max_length=150, description="Отчество")

    role: UserRole = Field(default=UserRole.ACCOUNTANT, description="Должность")
    department_id: UUID | None = Field(default=None, description="ID отдела")

    employment_status: EmploymentStatus = Field(default=EmploymentStatus.PROBATION, description="Статус оформления")

    probation_end_date: date | None = Field(default=None, description="Дата окончания испытательного срока")
    contract_start_date: date | None = Field(default=None, description="Дата начала контракта")
    contract_end_date: date | None = Field(default=None, description="Дата окончания контракта")


class EmployeeUpdate(Schema):
    """
    Схема для частичного обновления кадровых данных сотрудника (PATCH).
    """

    model_config = ConfigDict(
        extra="forbid",  # Запрет лишних полей (защита от опечаток фронта)
        str_strip_whitespace=True,  # Автоматически убирать лишние пробелы в начале/конце строк
    )

    first_name: str | None = Field(default=None, min_length=2, max_length=150, description="Обновить имя")
    last_name: str | None = Field(default=None, min_length=2, max_length=150, description="Обновить фамилию")
    middle_name: str | None = Field(default=None, max_length=150, description="Обновить отчество")

    role: UserRole | None = Field(default=None, description="Обновить должность")
    department_id: UUID | None = Field(default=None, description="Обновить ID отдела")

    employment_status: EmploymentStatus | None = Field(default=None, description="Обновить статус оформления")

    probation_end_date: date | None = Field(default=None, description="Обновить дату окончания испытательного срока")
    contract_start_date: date | None = Field(default=None, description="Обновить дату начала контракта")
    contract_end_date: date | None = Field(default=None, description="Обновить дату окончания контракта")


class FireEmployeeIn(Schema):
    """
    Схема для процесса увольнения сотрудника.
    """

    model_config = ConfigDict(extra="forbid")  # Запрет лишних полей (защита от опечаток фронта)

    successor_id: UUID | None = Field(
        default=None,
        description="ID сотрудника, которому будут переданы все клиенты увольняемого",  # The Handover Pattern
    )
