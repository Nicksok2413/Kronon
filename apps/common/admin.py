"""
Базовая админка для всего проекта.
"""

import uuid
from collections.abc import Callable
from typing import Any, TypeVar, cast

from django.contrib import admin, messages
from django.db.models import Model, QuerySet
from django.forms import BaseFormSet, BaseModelForm
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse
from django.utils.html import format_html
from django.utils.safestring import SafeString
from django.utils.translation import gettext_lazy as _
from loguru import logger
from pghistory import context as pghistory_context
from sentry_sdk import set_tag

# Generic тип для моделей, ограниченный базовым классом Model
_MT = TypeVar("_MT", bound=Model)
# Generic тип для возвращаемого значения оборачиваемой функции
_RT = TypeVar("_RT")


class SoftDeleteFilter(admin.SimpleListFilter):
    """Фильтр для разделения активных и удаленных записей."""

    title = _("Статус удаления")
    parameter_name = "soft_deleted"

    def lookups(self, request: HttpRequest, model_admin: admin.ModelAdmin[Any]) -> list[tuple[str, Any]]:
        return [
            ("active", _("Активные")),
            ("deleted", _("Удаленные")),
        ]

    def queryset(self, request: HttpRequest, queryset: QuerySet[_MT]) -> QuerySet[_MT] | None:
        # Используем методы из SoftDeleteQuerySet
        if self.value() == "active":
            # active_func = getattr(queryset, "active", None)
            # return active_func() if callable(active_func) else queryset
            return queryset.filter(deleted_at__isnull=True)

        if self.value() == "deleted":
            # deleted_func = getattr(queryset, "deleted", None)
            # return deleted_func() if callable(deleted_func) else queryset
            return queryset.filter(deleted_at__isnull=False)

        return queryset


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

    # Добавляем фильтр в список стандартных
    list_filter = (SoftDeleteFilter,)

    # Меняем шаблон формы карточки объекта?
    change_form_template = "admin/common/basemodel/change_form.html"

    def get_queryset(self, request: HttpRequest) -> QuerySet[_MT]:
        """Возвращает QuerySet со всеми записями (включая удаленные)."""
        # По умолчанию админка должна видеть все объекты
        return super().get_queryset(request).all()

    # --- UI helpers ---

    @admin.display(description=_("Статус"))
    def soft_delete_status(self, obj: _MT) -> SafeString:
        """
        Визуальное отображение статуса записи (активна/удалена).

        Args:
            obj: Экземпляр модели.

        Returns:
            HTML-строка с цветным индикатором статуса.
        """

        deleted_at = getattr(obj, "deleted_at", None)

        # white-space: nowrap — чтобы текст не разрывался
        # min-width: 60px — гарантирует, что колонка не сожмется слишком сильно
        style = "text-align: center; white-space: nowrap; display: inline-block; min-width: 60px;"

        if deleted_at:
            date = deleted_at.strftime("%d.%m.%y %H:%M")
            return format_html('<span style="color:red; font-weight: bold; {}">✘ Удален<br>{}</span>', style, date)

        return format_html('<span style="color:green; {}">✔ Активен</span>', style)

    # --- Audit ---

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

        # Склеиваем Correlation ID во все системы (Sentry - Loguru - pghistory)
        set_tag("correlation_id", correlation_id)

        with logger.contextualize(correlation_id=correlation_id):
            with pghistory_context(correlation_id=correlation_id, service="Admin"):
                return func(*args, **kwargs)

    # --- Object manipulations ---

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

    def delete_model(self, request: HttpRequest, obj: _MT) -> None:
        """
        Стандартная кнопка 'Удалить'.
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

    def get_urls(self) -> list[URLPattern]:
        """
        Добавляет кастомные URL'ы для объекта админки.

        'restore': для восстановления после мягкого удаления.
        'hard_delete': для физического удаления (Hard Delete).
        """

        app_label, model_name = self.model._meta.app_label, self.model._meta.model_name

        # Кастомные URL'ы
        custom_urls = [
            path(
                "<path:object_id>/restore/",
                self.admin_site.admin_view(self.restore_view),
                name=f"{app_label}_{model_name}_restore",
            ),
            path(
                "<path:object_id>/hard-delete/",
                self.admin_site.admin_view(self.hard_delete_view),
                name=f"{app_label}_{model_name}_hard_delete",
            ),
        ]

        # Базовые URL'ы
        urls = super().get_urls()

        # Расширяем URL'ы
        return custom_urls + urls

    def restore_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        """Обработка восстановления после мягкого удаления."""
        obj = self.get_object(request, object_id)

        if obj:
            restore_func = getattr(obj, "restore", obj.delete)
            self._run_with_audit(request, restore_func)

        self.message_user(request, "Объект восстановлен.", messages.SUCCESS)

        return redirect("..")

    def hard_delete_view(self, request: HttpRequest, object_id: str) -> HttpResponse:
        """Обработка физического удаления с подтверждением (Hard Delete)."""

        obj = self.get_object(request, object_id)

        if not obj:
            return redirect("..")

        if request.method == "POST":
            # Выполняем хард-делит
            hard_delete_func = getattr(obj, "hard_delete", obj.delete)
            self._run_with_audit(request, hard_delete_func)

            self.message_user(request, "Объект полностью удален из базы данных.", messages.WARNING)

            # return redirect(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_changelist")
            return redirect(f"admin:{obj._meta.app_label}_{obj._meta.model_name}_changelist")

        opts = self.model._meta

        return TemplateResponse(
            request,
            "admin/delete_confirmation.html",
            {
                **self.admin_site.each_context(request),
                "object_name": str(opts.verbose_name),
                "object": obj,
                "opts": opts,
                "app_label": opts.app_label,
                "title": "Вы уверены?",
            },
        )

    def change_view(
        self, request: HttpRequest, object_id: str, form_url: str = "", extra_context: dict[str, Any] | None = None
    ) -> HttpResponse:
        """Добавляет ссылки на Restore и Hard Delete в контекст шаблона."""

        obj = self.get_object(request, object_id)

        extra_context = extra_context or {}

        if obj:
            info = obj._meta.app_label, obj._meta.model_name

            is_deleted = getattr(obj, "is_deleted", False)

            extra_context.update(
                {
                    "is_deleted": is_deleted,
                    "hard_delete_url": reverse(f"admin:{info[0]}_{info[1]}_hard_delete", args=[object_id]),
                    "restore_url": reverse(f"admin:{info[0]}_{info[1]}_restore", args=[object_id]),
                }
            )

        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    # --- Custom actions ---

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

        Добавляет возможность восстановления мягко удаленных записей.

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
