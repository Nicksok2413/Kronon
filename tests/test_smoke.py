import pytest
from django.conf import settings


@pytest.mark.django_db
def test_db_connection():
    """Проверяем, что тесты видят базу и правильный порт"""

    port = settings.DATABASES["default"].get("PORT")

    assert port in [5433, "5433"]  # В тестах должен быть 5433-й порт БД
