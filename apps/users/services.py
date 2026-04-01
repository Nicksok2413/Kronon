"""
Сервисы (Write Logic) для приложения Users (Internal HR).
"""

from typing import Any

from django.db import transaction
from django.utils import timezone
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

    # Логируем бизнес-контекст операции
    log.info(f"Hiring employee. Email: {data.email}, Role: {data.role}")

    try:
        # Генерируем временный пароль
        temporary_password = generate_temporary_password()

        # Синхронная функция для выполнения внутри пула потоков
        def _create_employee() -> User:
            employee = User.objects.create(**payload)
            employee.set_password(temporary_password)
            employee.save(update_fields=["password"])
            return employee

        # Выполняем _create_employee асинхронно через утилиту (функцию-обертку с аудитом)
        # Профиль будет создан автоматически через сигнал
        user = await aexecute_with_audit(audit_context=audit_context, sync_func=_create_employee)

        log.info(f"Employee hired. ID: {user.id}")

        # .acreate() возвращает "чистый" объект (ID и базовые поля)
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


async def fire_employee(user: User, payload: FireEmployeeIn, audit_context: dict[str, Any]) -> None:
    """
    Увольняет сотрудника (Soft Delete) и опционально передает его клиентов преемнику.
    Выполняется в асинхронной транзакции для гарантии консистентности.

    Args:
        user (User): Объект сотрудника.
        payload (FireEmployeeIn): ID сотрудника, которому будут переданы все клиенты увольняемого (по умолчанию None).
        audit_context (dict[str, Any]): Словарь контекста аудита.
    """
    # В payload.successor_id лежит либо ID сотрудника, которому будут переданы все клиенты увольняемого, либо None
    successor_id = payload.successor_id

    try:
        # # aatomic() - нативная асинхронная транзакция
        # async with transaction.aatomic():
        #     with pghistory_context(**audit_context):
        #
        #         # Если передан successor_id (Передача дел / Handover)
        #         if successor_id:
        #             # Проверяем, существует ли преемник и активен ли он
        #             successor = await User.objects.active().filter(id=successor_id).afirst()
        #
        #             if not successor:
        #                 raise ValueError("Сотрудник-преемник не найден или уже уволен.")
        #
        #             if successor.id == user.id:
        #                 raise ValueError("Нельзя передать дела самому себе.")
        #
        #             log.info(f"Transferring clients from {user.id} to successor {successor.id}...")
        #
        #             # Массово обновляем клиентов (pghistory запишет аудит благодаря триггерам БД)
        #             # .aupdate() - асинхронный массовый апдейт (очень быстрый)
        #             await Client.objects.filter(accountant_id=user.id).aupdate(accountant_id=successor.id)
        #             await Client.objects.filter(primary_accountant_id=user.id).aupdate(primary_accountant_id=successor.id)
        #             await Client.objects.filter(payroll_accountant_id=user.id).aupdate(payroll_accountant_id=successor.id)
        #             await Client.objects.filter(hr_specialist_id=user.id).aupdate(hr_specialist_id=successor.id)
        #
        #         # Мягкое увольнение (блокировка аккаунта и простановка deleted_at)
        #         await user.adelete()
        #
        # log.info(f"Employee {user.id} successfully fired.")

        # СИНХРОННАЯ функция, в которой работает transaction.atomic()
        def _fire_and_handover() -> None:
            with transaction.atomic():
                if successor_id:
                    # Валидация преемника внутри транзакции
                    successor = User.objects.filter(id=successor_id, is_active=True).first()
                    if not successor:
                        raise ValueError("Сотрудник-преемник не найден или уволен.") from None
                    if successor.id == user.id:
                        raise ValueError("Нельзя передать дела самому себе.") from None

                    # Массовый Update клиентов (запишется в аудит pghistory)
                    Client.objects.filter(accountant_id=user.id).update(accountant_id=successor.id)
                    Client.objects.filter(primary_accountant_id=user.id).update(primary_accountant_id=successor.id)
                    Client.objects.filter(payroll_accountant_id=user.id).update(payroll_accountant_id=successor.id)
                    Client.objects.filter(hr_specialist_id=user.id).update(hr_specialist_id=successor.id)

                # Синхронное мягкое увольнение
                now = timezone.now()
                user.deleted_at = now
                user.updated_at = now
                user.is_active = False
                user.save(update_fields=["deleted_at", "updated_at", "is_active"])

        # Запускаем всё разом через нашу утилиту
        await aexecute_with_audit(audit_context=audit_context, sync_func=_fire_and_handover)
        log.info(f"Employee {user.id} successfully fired.")

        # TODO (Future): Запустить таску Celery для отправки алерта Главбуху,
        # если successor_id был None (остались бесхозные клиенты)

    except Exception as exc:
        # Логируем контекст ошибки перед тем, как она уйдет в глобальный хендлер
        log.error(f"Error firing employee {user.id}: {exc}")
        raise
