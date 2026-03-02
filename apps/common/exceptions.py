"""
Custom exception handlers for API.
"""

from django.conf import settings
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from loguru import logger as log
from ninja import NinjaAPI
from ninja.errors import HttpError
from ninja.errors import ValidationError as NinjaValidationError
from pydantic import ValidationError

from apps.common.schemas import ErrorOut


def setup_exception_handlers(api: NinjaAPI) -> None:
    """
    Регистрация глобальных обработчиков исключений для Ninja API.

    Args:
        api: Экземпляр NinjaAPI, к которому привязываются обработчики.
    """

    @api.exception_handler(HttpError)
    def ninja_http_error_handler(request: HttpRequest, exc: HttpError) -> HttpResponse:
        """
        Перехват стандартных ошибок Ninja (403 Forbidden, 404 Not Found).

        Args:
            request: Объект входящего запроса.
            exc: Исключение HttpError.

        Returns:
            HttpResponse: 403 если прав нет, 404 если не найден.
        """
        response_data = ErrorOut(message=str(exc), code=f"http_error_{exc.status_code}")
        return api.create_response(request=request, data=response_data, status=exc.status_code)

    @api.exception_handler(NinjaValidationError)
    def ninja_validation_error_handler(request: HttpRequest, exc: NinjaValidationError) -> HttpResponse:
        """
        Обработка ошибок парсинга данных на входе (неверный JSON, отсутствуют поля).

        Args:
            request: Объект входящего запроса.
            exc: Исключение ValidationError от Ninja.

        Returns:
            HttpResponse: 422 с деталями ошибок.
        """
        response_data = ErrorOut(
            message="Ошибка валидации входных данных.",
            code="validation_error",
            details=exc.errors,
        )
        return api.create_response(request=request, data=response_data, status=422)

    @api.exception_handler(ValidationError)
    def pydantic_validation_error_handler(request: HttpRequest, exc: ValidationError) -> HttpResponse:
        """
        Обработка ошибок валидации Pydantic (если они возникли вручную).

        Args:
            request: Объект входящего запроса.
            exc: Исключение ValidationError от Pydantic.

        Returns:
            HttpResponse: 422 с деталями ошибок.
        """
        response_data = ErrorOut(
            message="Ошибка структуры данных.",
            code="pydantic_validation_error",
            details=exc.errors(),
        )
        return api.create_response(request=request, data=response_data, status=422)

    @api.exception_handler(IntegrityError)
    def integrity_error_handler(request: HttpRequest, exc: IntegrityError) -> HttpResponse:
        """
        Обработка ошибок целостности базы данных (Unique, ForeignKey).

        Args:
            request: Объект входящего запроса.
            exc: Исключение IntegrityError.

        Returns:
            HttpResponse: 409 для дубликатов или 400 для ошибок связей.
        """
        exc_msg = str(exc).lower()

        # Обработка дубликата УНП (уникальный индекс)
        if "unp" in exc_msg:
            response_data = (ErrorOut(message="Клиент с таким УНП уже существует.", code="duplicate_unp"),)
            return api.create_response(request=request, data=response_data, status=409)

        response_data = ErrorOut(message="Ошибка целостности данных в БД.", code="integrity_error")
        return api.create_response(request=request, data=response_data, status=400)

    @api.exception_handler(ValueError)
    def value_error_handler(request: HttpRequest, exc: ValueError) -> HttpResponse:
        """
        Обработка ошибок бизнес-логики через ValueError.

        Args:
            request: Объект входящего запроса.
            exc: Исключение ValueError.

        Returns:
            HttpResponse: 400 ответ.
        """
        response_data = ErrorOut(message=str(exc), code="business_logic_error")
        return api.create_response(request=request, data=response_data, status=400)

    @api.exception_handler(Exception)
    def global_exception_handler(request: HttpRequest, exc: Exception) -> HttpResponse:
        """
        Глобальный перехватчик необработанных исключений.

        В режиме DEBUG пробрасывает ошибку дальше для отображения трейсбека Django.
        В Production логирует ошибку через Loguru. Sentry перехватит её автоматически
        благодаря LoguruIntegration(event_level=ERROR).

        Args:
            request: Объект входящего запроса.
            exc: Любое необработанное исключение.

        Returns:
            HttpResponse: 500 ответ.
        """
        # В режиме DEBUG позволяем Django показать стандартную страницу с ошибкой
        if settings.DEBUG:
            raise exc

        log.error(f"Unhandled exception at {request.path}: {exc}", exc_info=True)

        response_data = ErrorOut(message="Внутренняя ошибка сервера.", code="internal_server_error")
        return api.create_response(request=request, data=response_data, status=500)
