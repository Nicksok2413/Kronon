import pytest
from django.conf import settings


@pytest.mark.django_db
def test_db_connection():
    """Проверяем, что тесты видят базу и правильный порт"""

    port = settings.DATABASES["default"].get("PORT")

    assert port in [5432, "5432"]  # В тестах должен быть прямой порт БД
