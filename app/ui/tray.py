# -*- coding: utf-8 -*-
"""Логика системного трея."""

import os

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QIcon, QPainter, QColor, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from app.core.app_config import APP_VERSION, COLORS, resource_path
from app.utils.logging_utils import log_message


def create_tray_icon(window) -> None:
    """Создание иконки в системном трее."""
    log_message("Начало создания иконки в трее...")

    if not QSystemTrayIcon.isSystemTrayAvailable():
        log_message("ОШИБКА: Системный трей недоступен! Ждем...")
        QTimer.singleShot(1000, window._create_tray_icon)
        return

    window.tray_icon = QSystemTrayIcon(window)

    icon_path = resource_path("logo.ico")
    if os.path.exists(icon_path):
        window.default_icon = QIcon(icon_path)
        log_message(f"Иконка загружена из файла: {icon_path}")
    else:
        window.default_icon = create_colored_icon(COLORS["accent"])
        log_message("Иконка создана программно")

    window.record_icon = create_colored_icon(COLORS["record"])

    window.tray_icon.setIcon(window.default_icon)
    window.tray_icon.setToolTip(f"Gemini Voice Assistant v{APP_VERSION}")

    tray_menu = QMenu()
    show_action = QAction("Показать", window)
    show_action.triggered.connect(window.show_window)
    tray_menu.addAction(show_action)

    logs_action = QAction("Открыть логи", window)
    logs_action.triggered.connect(window.open_log_viewer)
    tray_menu.addAction(logs_action)

    window.pause_action = QAction("Пауза", window)
    window.pause_action.setCheckable(True)
    window.pause_action.triggered.connect(window.toggle_pause)
    tray_menu.addAction(window.pause_action)

    quit_action = QAction("Выход", window)
    quit_action.triggered.connect(window.quit_application)
    tray_menu.addAction(quit_action)

    window.tray_icon.setContextMenu(tray_menu)
    window.tray_icon.activated.connect(window.on_tray_activated)

    window.tray_icon.show()
    log_message("✓ Иконка в трее установлена")

    QTimer.singleShot(500, window._check_tray_visibility)


def check_tray_visibility(window) -> None:
    if window.tray_icon.isVisible():
        log_message("✓ Иконка в трее подтверждена видимой")
    else:
        log_message("✗ Иконка невидима, повторная установка...")
        window.tray_icon.setIcon(window.default_icon)
        window.tray_icon.show()


def create_colored_icon(color: str) -> QIcon:
    """Создание цветной иконки программно."""
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setBrush(QColor(color))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawEllipse(8, 8, 48, 48)

    pen = painter.pen()
    pen.setColor(QColor(COLORS["white"]))
    pen.setWidth(2)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawEllipse(8, 8, 48, 48)

    painter.end()
    return QIcon(pixmap)


def toggle_pause(window) -> None:
    window.assistant.is_paused = window.pause_action.isChecked()
    log_message(f"Пауза: {window.assistant.is_paused}")


def on_tray_activated(window, reason) -> None:
    if reason == QSystemTrayIcon.ActivationReason.Trigger:
        window.show_window()
