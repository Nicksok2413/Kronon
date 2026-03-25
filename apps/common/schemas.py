"""
Common schemas of Kronon project
"""

from typing import Any

from ninja import Field, Schema


class ErrorOut(Schema):
    """
    Единый формат ответа с ошибкой.
    Используется для 400, 401, 403, 404, 409, 422 и 500 ответов.
    """

    message: str = Field(..., description="Человекочитаемое сообщение об ошибке")
    code: str = Field(..., description="Машинный код ошибки (например: validation_error, not_found)")
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
