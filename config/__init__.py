# Импортируем приложение Celery
from .celery import app as celery_app

# __all__ гарантирует, что celery_app будет экспортировано
__all__ = ("celery_app",)
