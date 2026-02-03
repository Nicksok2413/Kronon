"""
Централизованная настройка логирования (Loguru) для Django.
"""

import logging
import sys
from pathlib import Path
from typing import Protocol

from loguru import logger


# Определяем протокол (контракт), которому должен соответствовать объект настроек
class LoguruSettingsProtocol(Protocol):
    """Протокол для объекта настроек, используемых Loguru."""

    LOG_LEVEL: str
    LOGFILE_SIZE: str | int
    LOGFILE_COUNT: int
    BASE_DIR: Path


class InterceptHandler(logging.Handler):
    """
    Перехватывает логи стандартного модуля logging и перенаправляет их в Loguru.
    """

    def emit(self, record: logging.LogRecord) -> None:
        # Получаем соответствующий уровень Loguru
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = str(record.levelno)

        # Ищем caller frame (откуда был вызван лог, чтобы правильно отобразить stack trace)
        frame, depth = logging.currentframe(), 2

        while frame and frame.f_code.co_filename == logging.__file__:
            if frame.f_back:
                frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


def setup_loguru(settings: LoguruSettingsProtocol) -> None:
    """
    Настраивает Loguru и перехват стандартного logging.

    Args:
        settings (LoguruSettingsProtocol): Объект настроек, реализующий протокол LoguruSettingsProtocol
    """
    log_level = settings.LOG_LEVEL
    logs_dir = settings.BASE_DIR / "logs"

    # Создаем директорию, если нет (подавляем ошибку, если уже есть)
    try:
        logs_dir.mkdir(exist_ok=True)
    except OSError:
        pass  # Если права доступа не позволяют, loguru сам выругается в stderr

    # Удаляем стандартный обработчик (чтобы не дублировать в stderr)
    logger.remove()

    # Вывод в консоль
    logger.add(
        sys.stderr,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Вывод в файл (ротация + сжатие)
    try:
        logger.add(
            logs_dir / "kronon.log",
            level=log_level,
            rotation=f"{settings.LOGFILE_SIZE} MB",
            retention=settings.LOGFILE_COUNT,
            compression="zip",
            enqueue=True,  # Асинхронная запись для производительности
            encoding="utf-8",
        )
    except Exception as exc:
        # Если не удалось настроить файл (например, нет прав), пишем варнинг в консоль, но не падаем
        logger.warning(f"Ошибка при настройке логирования в файл: {exc}")

    # Перехват стандартных логгеров Django
    # Отключаем стандартные хендлеры Django, чтобы они не писали в консоль сами
    logging.root.handlers = [InterceptHandler()]
    logging.root.setLevel(log_level)

    # Перехватываем конкретные логгеры (важно для библиотек)
    for name in logging.root.manager.loggerDict.keys():
        logging.getLogger(name).handlers = []
        logging.getLogger(name).propagate = True

    logger.info(f"Loguru сконфигурирован. Уровень: {log_level}")
