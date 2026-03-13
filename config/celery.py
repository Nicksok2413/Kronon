import os
import uuid
from typing import Any

from celery import Celery, Task
from celery.signals import before_task_publish
from loguru import logger

# Используем pghistory для трекинга контекста celery tasks
from pghistory import context as pghistory_context

# Устанавливаем переменную окружения, чтобы Celery знал, где искать настройки Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


class PghistoryTask(Task):
    """
    Базовый класс задач Celery с интеграцией аудита pghistory и логирования.
    Автоматически добавляет имя задачи в контекст аудита.
    """

    def __call__(self, *args: Any, **kwargs: Any):  # type: ignore
        # Извлекаем Trace ID 'correlation_id' из заголовков сообщения (прилетает из Django)
        # Если задача запущена не из веба (например, через beat) - генерим новый ID
        correlation_id = self.request.get("correlation_id") or str(uuid.uuid7())

        # Связываем контекст для Loguru (логи воркера) и контекст для pghistory (записи в БД)
        with logger.contextualize(correlation_id=correlation_id):
            with pghistory_context(correlation_id=correlation_id, service="Celery", celery_task=self.name):
                return super().__call__(*args, **kwargs)


@before_task_publish.connect
def add_correlation_id_to_headers(headers: dict, **kwargs: Any) -> None:
    """Автоматически подхватывает ID из текущего контекста Loguru и упаковывает его в транспортный заголовок Celery."""
    correlation_id = None

    # "Патчим" временный логгер, чтобы просто вытащить из его контекста Trace ID 'correlation_id'
    # Это официальный и безопасный способ доступа к extra-полям в Loguru
    def capture(record):
        nonlocal correlation_id
        correlation_id = record["extra"].get("correlation_id")

    logger.patch(capture).debug("Checking context")  # Этот лог никуда не уйдет

    if correlation_id and correlation_id != "-":
        headers["correlation_id"] = correlation_id


# Создаем экземпляр приложения Celery
app = Celery("kronon")

# Загружаем конфигурацию из настроек Django
app.config_from_object("django.conf:settings", namespace="CELERY")

# Подменяем базовый класс задачи
app.Task = PghistoryTask

# Автоматически обнаруживаем и регистрируем задачи из всех файлов tasks.py в установленных приложениях Django
app.autodiscover_tasks()
