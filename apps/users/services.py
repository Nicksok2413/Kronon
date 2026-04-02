"""
Сервисы (Write Logic) для приложения Users (Internal HR).
"""

from typing import Any
from uuid import UUID

from django.db import transaction
from loguru import logger as log

from apps.audit.utils import aexecute_with_audit
from apps.clients.models import Client
from apps.common.utils.security import generate_temporary_password
from apps.users.models import User
from apps.users.schemas.internal_hr import EmployeeCreate, EmployeeUpdate, FireEmployeeIn
from apps.users.selectors import get_user_by_id


async def hire_employee(data: EmployeeCreate, audit_context: dict[str, Any]) -> tuple[User, str]:
    """
    Нанимает нового сотрудника, создает профиль и генерирует временный пароль.

    Args:
        data (EmployeeCreate): Валидированные входные данные из API.
        audit_context (dict[str, Any]): Словарь контекста аудита.

    Returns:
        tuple (User, str): Созданный объект сотрудника с подгруженными связями, временный пароль.
    """
    # Формируем payload для полей модели
    # exclude_unset=True: берем только то, что пришло с фронта
    payload = data.model_dump(exclude_unset=True)

    # Генерируем временный пароль и добавляем его в payload
    temporary_password = generate_temporary_password()
    payload["password"] = temporary_password

    # Логируем бизнес-контекст операции
    log.info(f"Hiring employee. Email: {data.email}, Role: {data.role}")

    try:
        # Выполняем кастомный .create_user() асинхронно через утилиту (функцию-обертку с аудитом)
        # Профиль будет создан автоматически через сигнал
        user = await aexecute_with_audit(audit_context=audit_context, sync_func=User.objects.create_user, **payload)

        log.info(f"Employee hired. ID: {user.id}")

        # Делаем рефреш через селектор с подгрузкой связей (department, profile) для корректного ответа API
        full_user = await get_user_by_id(user.id, status="active")

        # Теоретически невозможно, что его нет, но для mypy:
        if not full_user:
            log.critical(f"Employee {user.id} disappeared after creation!")
            raise RuntimeError("Employee not found after creation.")

        # Возвращаем созданный объект с полными данными и временный пароль
        return full_user, temporary_password

    except Exception as exc:
        # Логируем контекст ошибки перед тем, как она уйдет в глобальный хендлер
        log.error(f"Error hiring employee (Email: {data.email}): {exc}")
        raise


async def update_employee(user: User, data: EmployeeUpdate, audit_context: dict[str, Any]) -> User:
    """
    Выполняет частичное обновление кадровых данных сотрудника (перевод, продление контракта).

    Обрабатывает как стандартные поля модели, так и вложенное JSON-поле
    contact_info через специальный метод модели.

    Args:
        user (User): Объект сотрудника (уже полученный из БД).
        data (EmployeeUpdate): Данные для обновления.
        audit_context (dict[str, Any]): Словарь контекста аудита.

    Returns:
        User: Обновленный объект сотрудника с подгруженными связями.
    """
    # Формируем payload для полей модели
    # exclude_unset=True: берем только то, что пришло с фронта
    payload = data.model_dump(exclude_unset=True)

    # Early Exit
    if not payload:
        log.debug(f"Empty payload for employee {user.id}. Skipping update.")
        return user

    # Логируем, какие поля меняются
    log.info(f"Updating employee {user.id}. Fields: {list(payload.keys())}")

    try:
        # Обновляем поля
        for field, value in payload.items():
            setattr(user, field, value)

        # Выполняем .save() асинхронно через утилиту (функцию-обертку с аудитом)
        await aexecute_with_audit(audit_context=audit_context, sync_func=user.save)

        log.debug(f"Employee updated: {user.id}")

        # Делаем рефреш через селектор с подгрузкой связей (актуальные связи и updated_at) для корректного ответа API
        updated_user = await get_user_by_id(user_id=user.id, status="all")

        # Теоретически невозможно, что его нет, но для mypy:
        if not updated_user:
            log.critical(f"Employee {user.id} disappeared after update!")
            raise RuntimeError("Employee not found after update.")

        # Возвращаем актуальные данные
        return updated_user

    except Exception as exc:
        # Логируем контекст ошибки перед тем, как она уйдет в глобальный хендлер
        log.error(f"Error updating employee {user.id}: {exc}")
        raise


def _fire_and_handover(user: User, successor_id: UUID | None) -> None:
    """
    Синхронная утилита, содержит логику увольнения сотрудника (Soft Delete) и передачи дел внутри транзакции.
    Обеспечивает атомарность через транзакцию, но выполняется асинхронно через утилиту aexecute_with_audit.

    Args:
        user (User): Объект увольняемого сотрудника.
        successor_id (UUID | None): ID сотрудника, которому будут переданы все клиенты увольняемого или None.
    """
    # Логируем бизнес-контекст операции
    log.info(f"Starting offboarding for {user.id}. Successor: {successor_id}")

    with transaction.atomic():
        # Валидация преемника внутри транзакции
        if successor_id:
            # Ищем преемника
            successor = User.objects.filter(id=successor_id, is_active=True).first()

            # Проверяем существование преемника
            if not successor:
                raise ValueError("Сотрудник-преемник не найден или уволен.")

            # Проверяем что преемник - это не сам увольняемый сотрудник
            if successor.id == user.id:
                raise ValueError("Нельзя передать дела самому себе.")

            log.info(f"Transferring clients from {user.id} to successor {successor_id}...")

            # Массово обновляем клиентов (запишется в аудит pghistory благодаря триггерам БД)
            Client.objects.filter(accountant_id=user.id).update(accountant_id=successor.id)
            Client.objects.filter(primary_accountant_id=user.id).update(primary_accountant_id=successor.id)
            Client.objects.filter(payroll_accountant_id=user.id).update(payroll_accountant_id=successor.id)
            Client.objects.filter(hr_specialist_id=user.id).update(hr_specialist_id=successor.id)

        # Мягкое увольнение (блокировка аккаунта и простановка deleted_at)
        user.delete()


async def fire_employee(user: User, data: FireEmployeeIn, audit_context: dict[str, Any]) -> None:
    """
    Увольняет сотрудника (Soft Delete) и опционально передает его клиентов преемнику (Handover).

    Args:
        user (User): Объект сотрудника.
        data (FireEmployeeIn): ID сотрудника, которому будут переданы все клиенты увольняемого или None.
        audit_context (dict[str, Any]): Словарь контекста аудита.
    """
    try:
        # Запускаем асинхронно через утилиту (функцию-обертку с аудитом)
        await aexecute_with_audit(
            audit_context=audit_context,
            sync_func=_fire_and_handover,  # Синхронная функция, в которой работает transaction.atomic()
            user=user,
            successor_id=data.successor_id,
        )

        log.info(f"Employee {user.id} successfully fired.")

        # если successor_id был None (остались бесхозные клиенты)
        # TODO (Future): Запустить таску Celery для отправки алёрта Главбуху

    except Exception as exc:
        # Логируем контекст ошибки перед тем, как она уйдет в глобальный хендлер
        log.error(f"Error firing employee {user.id}: {exc}")
        raise
