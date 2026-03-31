"""
Глобальные схемы данных (DTO) для всего проекта.
"""

from typing import Any

from ninja import Field, Schema


class ErrorOut(Schema):
    """
    Унифицированная схема для возврата ошибок API.
    Гарантирует, что фронтенд всегда получает ошибки в одном формате.
    Используется для 400, 401, 403, 404, 409, 422 и 500 ответов.
    """

    message: str = Field(..., description="Человекочитаемое сообщение об ошибке")
    code: str = Field(..., description="Машинный код ошибки (например: not_found, permission_denied)")
    details: dict[str, Any] | list[Any] | None = Field(
        default=None,
        description="Детали ошибки (например, список невалидных полей)",
    )


# Стандартный набор ответов с ошибками (для DRY)
STANDARD_ERRORS = {
    400: ErrorOut,
    401: ErrorOut,
    403: ErrorOut,
    404: ErrorOut,
    409: ErrorOut,
    422: ErrorOut,
    500: ErrorOut,
}
