"""
Middleware для сбора контекста аудита.
"""

from typing import Any

from django.http import HttpRequest
from pghistory.middleware import HistoryMiddleware


class KrononHistoryMiddleware(HistoryMiddleware):
    """
    Расширенный middleware для pghistory.
    Добавляет IP адрес, метод, источник и email пользователя в контекст.
    """

    def get_context(self, request: HttpRequest) -> dict[str, Any]:
        """
        Формирует словарь контекста.

        Базовый метод добавляет 'user' (ID) и 'url' (эндпойнт).

        Добавляем:
            'ip': IP адрес,
            'method': HTTP-метод,
            'app_source': источник (API/Web),
            'user_email': email пользователя.
        """
        # Базовый контекст
        base_context = super().get_context(request)

        # Получаем IP (с учетом прокси)
        ip = request.META.get("HTTP_X_FORWARDED_FOR")

        if ip:
            ip = ip.split(",")[0]
        else:
            ip = request.META.get("REMOTE_ADDR")

        # Полезно сохранить email, чтобы он остался в истории при удалении юзера
        user_email = getattr(request.user, "email", None) if request.user.is_authenticated else None

        # Обновляем словарь контекста
        return base_context | {
            "ip": ip,
            "method": request.method,
            "app_source": "API/Web",
            "user_email": user_email,
        }
