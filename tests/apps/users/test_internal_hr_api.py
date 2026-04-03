"""
Интеграционные тесты для Внутреннего HR API.
"""

from time import perf_counter
from typing import Any

from asgiref.sync import sync_to_async
from django.test import AsyncClient

from apps.common.schemas import ErrorOut
from apps.users.models import User, UserRole
from apps.users.schemas.internal_hr import HireResponseOut
from tests.utils.base import BaseAPITest
from tests.utils.factories import ClientFactory, DepartmentFactory, UserFactory


class TestInternalHRAPI(BaseAPITest):
    """
    Тестирование HR эндпоинтов (Найм, Обновление, Увольнение с передачей дел).
    """

    @property
    def endpoint(self) -> str:
        return self.get_url("internal-hr/employees")

    async def test_access_denied_for_accountant(self, auth_client: AsyncClient) -> None:
        """
        Проверка RBAC: обычный бухгалтер не может получить доступ к HR-модулю.

        Args:
            auth_client (AsyncClient): Авторизованный асинхронный клиент (с правами бухгалтера).
        """

        # --- Act (действие) ---

        # Выполняем запрос
        start = perf_counter()
        response = await auth_client.get(self.endpoint)
        elapsed_time = perf_counter() - start

        data: dict[str, Any] = response.json()

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=response, expected_status=403)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)
        # Валидация схемы
        await self.validate_schema(data=data, schema=ErrorOut)

        assert "требуются права внутреннего hr" in data["message"].lower()

    async def test_hire_employee_success(self, internal_hr_client: AsyncClient) -> None:
        """
        Проверка успешного найма сотрудника.

        Args:
            internal_hr_client (AsyncClient): Авторизованный асинхронный клиент (с правами внутреннего HR).
        """

        # --- Arrange (подготовка) ---

        # Подготавливаем данные
        email = "new_hire@kronon.by"
        department = await sync_to_async(DepartmentFactory)()
        payload = {
            "email": email,
            "first_name": "John",
            "last_name": "Doe",
            "role": "accountant",
            "department_id": str(department.id),
            "employment_status": "probation",
        }

        # --- Act (действие) ---

        # Внутренний нанимает сотрудника
        start = perf_counter()
        hire_response = await internal_hr_client.post(self.endpoint, data=payload, content_type="application/json")
        elapsed_time = perf_counter() - start

        data = hire_response.json()

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=hire_response, expected_status=201)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)
        # Валидация схемы
        await self.validate_schema(data, schema=HireResponseOut)

        assert data["employee"]["email"] == email
        assert len(data["temporary_password"]) >= 12  # Временный пароль сгенерирован

    async def test_fire_employee_with_handover(self, internal_hr_client: AsyncClient) -> None:
        """
        Проверка увольнения с паттерном передачи дел (Handover).
        Проверяем, что клиенты корректно переписываются на преемника.

        Args:
            internal_hr_client (AsyncClient): Авторизованный асинхронный клиент (с правами внутреннего HR).
        """

        # --- Arrange (подготовка) ---

        # Создаем увольняемого, преемника и клиента
        leaving_user = await sync_to_async(UserFactory)(role=UserRole.ACCOUNTANT)
        successor_user = await sync_to_async(UserFactory)(role=UserRole.ACCOUNTANT)

        # Клиент, который закреплен за увольняемым (как ведущий бухгалтер и зарплатник)
        client = await sync_to_async(ClientFactory)(accountant=leaving_user, payroll_accountant=leaving_user)

        payload = {"successor_id": str(successor_user.id)}

        # --- Act (действие) ---

        # Внутренний HR увольняет сотрудника
        start = perf_counter()
        fire_response = await internal_hr_client.delete(
            f"{self.endpoint}{leaving_user.id}",
            data=payload,
            content_type="application/json",
        )
        elapsed_time = perf_counter() - start

        # --- Assert (проверка) ----

        # Статус код
        await self.assert_status(response=fire_response, expected_status=204)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        # Проверяем, что уволенный заблокирован (Soft Delete)
        await leaving_user.arefresh_from_db()
        assert not leaving_user.is_active
        assert leaving_user.deleted_at is not None

        # Проверяем передачу дел: Клиент теперь должен принадлежать successor_user
        await client.arefresh_from_db()
        assert client.accountant_id == successor_user.id
        assert client.payroll_accountant_id == successor_user.id

    async def test_fire_idempotency_early_exit(self, internal_hr_client: AsyncClient) -> None:
        """
        Проверка Early Exit: увольнение уже уволенного возвращает 204.

        Args:
            internal_hr_client (AsyncClient): Авторизованный асинхронный клиент (с правами внутреннего HR).
        """

        # --- Arrange (подготовка) ---

        # Создаем уволенного (неактивного) сотрудника
        already_fired_user = await sync_to_async(UserFactory)(is_active=False)

        # --- Act (действие) ---

        # Внутренний HR увольняет уже уволенного сотрудника
        start = perf_counter()
        fire_response = await internal_hr_client.delete(
            f"{self.endpoint}{already_fired_user.id}",
            data={},
            content_type="application/json",
        )
        elapsed_time = perf_counter() - start

        # --- Assert (проверка) ----

        # Статус код - ожидаем 204, потому что целевое состояние (сотрудник уволен) уже достигнуто
        await self.assert_status(response=fire_response, expected_status=204)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

    async def test_fire_self_not_allowed(self, internal_hr_client: AsyncClient, internal_hr_user: User) -> None:
        """
        Бизнес-инвариант: нельзя уволить самого себя через API.

        Args:
            internal_hr_client (AsyncClient): Авторизованный асинхронный клиент (с правами внутреннего HR).
            internal_hr_user (User): Внутренний HR.
        """

        # --- Act (действие) ---

        # Внутренний HR пытается уволить сам себя
        start = perf_counter()
        fire_response = await internal_hr_client.delete(
            f"{self.endpoint}{internal_hr_user.id}",
            data={},
            content_type="application/json",
        )
        elapsed_time = perf_counter() - start

        data: dict[str, Any] = fire_response.json()

        # --- Assert (проверка) ----

        # Статус код (глобальный обработчик ValueError должен вернуть 400)
        await self.assert_status(response=fire_response, expected_status=400)
        # Время ответа API
        await self.assert_performance(elapsed_time=elapsed_time, max_ms=500)

        assert "не можете уволить сами себя" in data["message"].lower()
