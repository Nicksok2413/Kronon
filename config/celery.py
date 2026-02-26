import os
from typing import Any

from celery import Celery, Task

# Используем pghistory для трекинга контекста celery tasks
from pghistory import context as pghistory_context

# Устанавливаем переменную окружения, чтобы Celery знал, где искать настройки Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


class PghistoryTask(Task):
    """
    Базовый класс задач Celery с интеграцией pghistory.
    Автоматически добавляет имя задачи в контекст аудита.
    """

    def __call__(self, *args: Any, **kwargs: Any):  # type: ignore
        # В БД в поле pgh_context будет: {"app_source": "Celery", "celery_task": "..."}
        with pghistory_context(app_source="Celery", celery_task=self.name):
            return super().__call__(*args, **kwargs)


# Создаем экземпляр приложения Celery
app = Celery("kronon")

# Загружаем конфигурацию из настроек Django
app.config_from_object("django.conf:settings", namespace="CELERY")

# Подменяем базовый класс задачи
app.Task = PghistoryTask

# Автоматически обнаруживаем и регистрируем задачи из всех файлов tasks.py в установленных приложениях Django
app.autodiscover_tasks()
