"""
Базовая админка для всего проекта.
"""

import uuid
from collections.abc import Callable
from typing import Any, TypeVar, cast

from django.contrib import admin
from django.db.models import Model, QuerySet
from django.forms import BaseFormSet, BaseModelForm
from django.http import HttpRequest
from loguru import logger
from pghistory import context as pghistory_context

# Generic тип для моделей, ограниченный базовым классом Model
_MT = TypeVar("_MT", bound=Model)
# Generic тип для возвращаемого значения оборачиваемой функции
_RT = TypeVar("_RT")


class KrononBaseAdmin(admin.ModelAdmin[_MT]):
    """
    Базовый класс админки с поддержкой аудита и трассировки.

    Обеспечивает автоматическую передачу Correlation ID в логи (Loguru)
    и контекст базы данных (pghistory). Гарантирует корректную работу
    логики Soft Delete при одиночных и массовых операциях.

    - Исключение N+1 через prefetch_related

    Attributes:
        show_full_result_count (bool): Отключает ресурсоемкий SELECT COUNT(*) для пагинации.
        list_per_page (int): Количество записей на одной странице списка.
    """

    # Не считаем общее количество страниц на миллионах строк истории
    show_full_result_count = False

    # Немного ускорит админку на больших объёмах
    list_per_page = 50

    @staticmethod
    def _get_correlation_id(request: HttpRequest) -> str:
        """
        Извлекает существующий или генерирует новый Correlation ID.

        Args:
            request (HttpRequest): Объект входящего HTTP-запроса.

        Returns:
            str: Строка с уникальным идентификатором корреляции (UUID7).
        """
        correlation_id = getattr(request, "correlation_id", None)
        return cast(str, correlation_id) if correlation_id else str(uuid.uuid7())

    def _run_with_audit(self, request: HttpRequest, func: Callable[..., _RT], *args: Any, **kwargs: Any) -> _RT:
        """
        Оборачивает выполнение функции в контекст аудита и трассировки.

        Создает контекст для Loguru (поле extra['correlation_id']) и pghistory (JSONB контекст события).

        Args:
            request (HttpRequest): Объект входящего HTTP-запроса.
            func (Callable[..., _RT]): Функция или метод для выполнения (например, super().save_model).
            *args (Any): Позиционные аргументы для вызываемой функции.
            **kwargs (Any): Именованные аргументы для вызываемой функции.

        Returns:
            _RT: Результат выполнения переданной функции `func`.
        """
        # Извлекаем или генерируем Correlation ID
        correlation_id = self._get_correlation_id(request)

        with logger.contextualize(correlation_id=correlation_id):
            with pghistory_context(correlation_id=correlation_id, service="Admin"):
                return func(*args, **kwargs)

    def save_model(self, request: HttpRequest, obj: _MT, form: BaseModelForm[_MT], change: bool) -> None:
        """
        Сохраняет объект модели с регистрацией контекста аудита.

        Args:
            request (HttpRequest): Объект входящего HTTP-запроса.
            obj (_MT): Экземпляр сохраняемой модели.
            form (BaseModelForm[_MT]): Форма, использованная для редактирования/создания.
            change (bool): Флаг, указывающий на изменение существующего объекта.
        """
        self._run_with_audit(request, super().save_model, request, obj, form, change)

    def delete_model(self, request: HttpRequest, obj: _MT) -> None:
        """
        Удаляет объект модели, используя логику Soft Delete.

        Args:
            request (HttpRequest): Объект входящего HTTP-запроса.
            obj (_MT): Экземпляр удаляемой модели.
        """
        self._run_with_audit(request, obj.delete)

    def delete_queryset(self, request: HttpRequest, queryset: QuerySet[_MT]) -> None:
        """
        Массово помечает объекты как удаленные (Bulk Soft Delete).

        Args:
            request (HttpRequest): Объект входящего HTTP-запроса.
            queryset (QuerySet[_MT]): Набор объектов для удаления.
        """
        self._run_with_audit(request, queryset.delete)

    def save_formset(
        self,
        request: HttpRequest,
        form: BaseModelForm[_MT],
        formset: BaseFormSet[Any],
        change: bool,
    ) -> None:
        """
        Сохраняет связанные наборы форм (Inlines) с регистрацией контекста.

        Args:
            request (HttpRequest): Объект входящего HTTP-запроса.
            form (BaseModelForm[_MT]): Основная форма родительского объекта.
            formset (BaseFormSet[_MT]): Набор форм связанных объектов.
            change (bool): Флаг изменения существующего родителя.
        """
        self._run_with_audit(request, super().save_formset, request, form, formset, change)

    # --- ACTIONS ---

    @admin.action(description="Восстановить выбранные записи")
    def restore_selected(self, request: HttpRequest, queryset: QuerySet[_MT]) -> None:
        """
        Действие админки для восстановления мягко удаленных записей.

        Args:
            request (HttpRequest): Объект входящего HTTP-запроса.
            queryset (QuerySet[_MT]): Набор восстанавливаемых объектов.
        """

        # Определяем внутреннюю функцию, которую будем аудировать
        # Она не должна принимать аргументов, так как queryset уже в замыкании
        def _do_restore() -> Any:
            restore_func = getattr(queryset, "restore", None)

            if callable(restore_func):
                return restore_func()

            return 0

        # Вызываем через обертку
        count = self._run_with_audit(request, _do_restore)

        if count > 0:
            self.message_user(request, f"Успешно восстановлено объектов: {count}")

    def get_actions(self, request: HttpRequest) -> dict[str, Any]:
        """
        Расширяет список доступных действий админки.

        Args:
            request (HttpRequest): Объект входящего HTTP-запроса.

        Returns:
            dict[str, Any]: Словарь доступных действий, где ключ — имя метода.
        """
        actions: dict[str, Any] = super().get_actions(request)

        # Получаем описание из атрибута, который добавил декоратор @admin.action
        description = getattr(self.restore_selected, "short_description", "Restore")

        actions["restore_selected"] = (
            self.__class__.restore_selected,  # Передаем как unbound method
            "restore_selected",
            description,
        )

        return actions
