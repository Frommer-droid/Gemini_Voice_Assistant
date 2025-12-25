# -*- coding: utf-8 -*-
import logging
from logging.handlers import RotatingFileHandler

from app.core.app_config import HISTORY_FILE, LOG_FILE


def setup_logging():
    """Настройка логирования с автоматической ротацией"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # ИСПРАВЛЕНО: Явно указываем UTF-8 и errors='replace'
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=200 * 1024,
        backupCount=1,
        encoding="utf-8",
        errors="replace",  # Добавлено: заменяет некорректные символы
    )

    # ИСПРАВЛЕНО: Форматтер с явной поддержкой Unicode
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def setup_history_logging():
    """Настройка логирования истории с ротацией"""
    history_logger = logging.getLogger("history")
    history_logger.setLevel(logging.INFO)

    if history_logger.hasHandlers():
        history_logger.handlers.clear()

    handler = RotatingFileHandler(
        HISTORY_FILE, maxBytes=500 * 1024, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    history_logger.addHandler(handler)
    return history_logger


logger = setup_logging()
history_logger = setup_history_logging()


def log_message(msg):
    """Логирование в файл"""
    try:
        logger.info(msg)
    except Exception:
        pass


def log_separator():
    """Добавляет разделитель в лог-файл"""
    try:
        logger.info("=" * 80)
    except Exception:
        pass


def reset_logger():
    """Пересоздаёт логгер после ручной очистки файла."""
    global logger
    logger = setup_logging()
    return logger
