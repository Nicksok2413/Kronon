"""
Централизованная настройка Sentry SDK.
"""
from logging import ERROR, INFO  # Стандартные уровни логирования для Sentry
from typing import Protocol

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.loguru import LoguruIntegration
from sentry_sdk.integrations.redis import RedisIntegration
from sentry_sdk.integrations.threading import ThreadingIntegration

from loguru import logger


# Определяем протокол (контракт), которому должен соответствовать объект настроек
class SentrySettingsProtocol(Protocol):
    """Протокол для объекта настроек, используемых Sentry."""
    SENTRY_DSN: str | None
    SENTRY_ENVIRONMENT: str
    DEBUG: bool


def setup_sentry(settings: SentrySettingsProtocol) -> None:
    """
    Инициализирует Sentry SDK, если задан DSN.

    Args:
        settings (SentrySettingsProtocol): Объект настроек, реализующий протокол SentrySettingsProtocol
    """
    sentry_dsn = settings.SENTRY_DSN

    if not sentry_dsn:
        # В режиме DEBUG отсутствие DSN - норма
        if not settings.DEBUG:
            logger.warning("SENTRY_DSN не установлен! Мониторинг отключен.")
        return

    # --- Определяем параметры Sentry ---

    # Частота семплирования для Performance Monitoring (Traces)
    traces_sample_rate = 1.0 if settings.DEBUG else 0.1  # 10% в проде, 100% в деве
    # Частота семплирования для Profiling
    profiles_sample_rate = 1.0 if settings.DEBUG else 0.1  # Аналогично трейсам

    logger.info(f"Инициализация Sentry (Env: {settings.SENTRY_ENVIRONMENT})...")

    try:
        sentry_sdk.init(
            dsn=sentry_dsn,
            environment=settings.SENTRY_ENVIRONMENT,
            # Настройка производительности
            traces_sample_rate=traces_sample_rate,
            profiles_sample_rate=profiles_sample_rate,
            # Интеграции
            integrations=[
                # Django (автоматически перехватывает 500 ошибки во вьюхах)
                DjangoIntegration(
                    transaction_style="url",
                    middleware_spans=True,
                    signals_spans=True,
                    cache_spans=True,
                ),
                # Celery (перехват ошибок в задачах)
                CeleryIntegration(),
                # Redis (мониторинг запросов к кэшу)
                RedisIntegration(),
                # Loguru (перехват error-логов как событий)
                LoguruIntegration(
                    level=INFO,  # Breadcrumbs
                    event_level=ERROR  # Events
                ),
                # Потоки (важно для Celery)
                ThreadingIntegration(propagate_hub=True),
            ],
        )
        logger.success("Sentry SDK успешно инициализирован.")

    except Exception as exc:
        logger.exception(f"Ошибка инициализации Sentry: {exc}")
