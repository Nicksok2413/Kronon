"""
Custom exception handlers for API.
"""

from django.conf import settings
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from loguru import logger
from ninja import NinjaAPI
from pydantic import ValidationError


def setup_exception_handlers(api: NinjaAPI) -> None:
    """Регистрация глобальных обработчиков исключений для Ninja API.

    Args:
        api: Экземпляр NinjaAPI, к которому привязываются обработчики.
    """

    @api.exception_handler(IntegrityError)
    def integrity_error_handler(request: HttpRequest, exc: IntegrityError) -> HttpResponse:
        """Обработка ошибок целостности базы данных (Unique, ForeignKey).

        Args:
            request: Объект входящего запроса.
            exc: Исключение IntegrityError.

        Returns:
            HttpResponse: 409 для дубликатов или 400 для ошибок связей.
        """
        exc_msg = str(exc).lower()

        # Обработка дубликата УНП (уникальный индекс)
        if "unp" in exc_msg:
            return api.create_response(
                request,
                {"message": "Клиент с таким УНП уже существует", "code": "duplicate_unp"},
                status=409,
            )

        return api.create_response(
            request,
            {"message": "Ошибка целостности данных в БД", "code": "integrity_error"},
            status=400,
        )

    @api.exception_handler(ValidationError)
    def pydantic_validation_error_handler(request: HttpRequest, exc: ValidationError) -> HttpResponse:
        """Обработка ошибок валидации Pydantic (если они возникли вручную).

        Args:
            request: Объект входящего запроса.
            exc: Исключение ValidationError от Pydantic.

        Returns:
            HttpResponse: 422 с деталями ошибок.
        """
        return api.create_response(
            request,
            {"message": "Ошибка валидации данных", "errors": exc.errors(), "code": "validation_error"},
            status=422,
        )

    @api.exception_handler(ValueError)
    def value_error_handler(request: HttpRequest, exc: ValueError) -> HttpResponse:
        """Обработка ошибок бизнес-логики через ValueError.

        Args:
            request: Объект входящего запроса.
            exc: Исключение ValueError.

        Returns:
            HttpResponse: 400 с текстом ошибки.
        """
        return api.create_response(
            request,
            {"message": str(exc), "code": "business_logic_error"},
            status=400,
        )

    @api.exception_handler(Exception)
    def global_exception_handler(request: HttpRequest, exc: Exception) -> HttpResponse:
        """Глобальный перехватчик необработанных исключений.

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

        logger.error(f"Необработанное исключение в {request.path}: {exc}", exc_info=True)

        return api.create_response(
            request,
            {"message": "Внутренняя ошибка сервера", "code": "internal_server_error"},
            status=500,
        )
