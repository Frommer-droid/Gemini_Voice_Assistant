# -*- coding: utf-8 -*-
"""Обработчики истории и логов."""

import os

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QFont

from app.core.app_config import COLORS, HISTORY_FILE, LOG_FILE
from app.utils.logging_utils import log_message
from app.ui.ui_dialogs import HistoryViewerWindow, LogViewerWindow


def update_history_combo(window) -> None:
    window.history_combo.clear()
    history_items = window.assistant.load_history_to_combo()
    for display_text, full_data in history_items:
        window.history_combo.addItem(display_text, full_data)


def open_log_viewer(window) -> None:
    if window.log_viewer is None or not window.log_viewer.isVisible():
        window.log_viewer = LogViewerWindow(LOG_FILE, window)
        width = window.assistant.settings.get("log_window_width")
        height = window.assistant.settings.get("log_window_height")
        font_size = window.assistant.settings.get("log_font_size")
        window.log_viewer.resize(width, height)
        window.log_viewer.text_edit.setFont(QFont("Consolas", font_size))
    window.log_viewer.show()
    window.log_viewer.raise_()
    window.log_viewer.activateWindow()
    window.log_viewer.load_logs()


def clear_logs(window) -> None:
    window.assistant.clear_log_file()
    if window.log_viewer and window.log_viewer.isVisible():
        window.log_viewer.load_logs()
    window.assistant.show_status("Логи очищены", COLORS["accent"], False)


def show_selected_history(window) -> None:
    current_data = window.history_combo.currentData()
    if current_data:
        if window.history_viewer is None or not window.history_viewer.isVisible():
            window.history_viewer = HistoryViewerWindow(current_data, window)
            width = window.assistant.settings.get("history_window_width")
            height = window.assistant.settings.get("history_window_height")
            font_size = window.assistant.settings.get("history_font_size", 10)
            window.history_viewer.resize(width, height)
            window.history_viewer.text_edit.setFont(QFont("Consolas", font_size))
        else:
            window.history_viewer.text_edit.setPlainText(current_data)
        window.history_viewer.show()


def clear_history(window) -> None:
    window.assistant.clear_history_file()
    update_history_combo(window)
    window.assistant.show_status("История очищена", COLORS["accent"], False)


def open_history_file(window) -> None:
    try:
        if not os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "w", encoding="utf-8"):
                pass
        opened = QDesktopServices.openUrl(QUrl.fromLocalFile(HISTORY_FILE))
    except Exception as exc:
        opened = False
        log_message(f"Ошибка открытия файла истории: {exc}")

    if opened:
        window.assistant.show_status("Файл истории открыт", COLORS["accent"], False)
    else:
        window.assistant.show_status(
            "Не удалось открыть файл истории", COLORS["btn_warning"], False
        )
