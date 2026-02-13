from typing import Annotated

from pydantic import AfterValidator

from apps.common.validators import validate_phone_pydantic

# AfterValidator прогонит значение через функцию валидации телефона после базовой проверки строки
PhoneNumber = Annotated[
    str,
    AfterValidator(validate_phone_pydantic),  # Проверяет формат телефона через phonenumbers
]
