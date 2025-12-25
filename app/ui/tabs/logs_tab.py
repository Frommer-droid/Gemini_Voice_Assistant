# -*- coding: utf-8 -*-
"""Вкладка логов."""

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def create_logs_tab(window) -> None:
    tab = QWidget()
    layout = QVBoxLayout(tab)

    size_group = QGroupBox("Окно логов")
    size_layout = QVBoxLayout(size_group)
    width_layout = QHBoxLayout()
    width_layout.addWidget(QLabel("Ширина:"))
    window.log_width_spin = QSpinBox()
    window.log_width_spin.setRange(300, 1200)
    window.log_width_spin.setValue(window.assistant.settings.get("log_window_width"))
    width_layout.addWidget(window.log_width_spin)
    size_layout.addLayout(width_layout)

    height_layout = QHBoxLayout()
    height_layout.addWidget(QLabel("Высота:"))
    window.log_height_spin = QSpinBox()
    window.log_height_spin.setRange(200, 1000)
    window.log_height_spin.setValue(window.assistant.settings.get("log_window_height"))
    height_layout.addWidget(window.log_height_spin)
    size_layout.addLayout(height_layout)

    font_layout = QHBoxLayout()
    font_layout.addWidget(QLabel("Размер шрифта:"))
    window.log_font_spin = QSpinBox()
    window.log_font_spin.setRange(6, 20)
    window.log_font_spin.setValue(window.assistant.settings.get("log_font_size"))
    font_layout.addWidget(window.log_font_spin)
    size_layout.addLayout(font_layout)
    layout.addWidget(size_group)

    logs_group = QGroupBox("Управление логами")
    logs_layout = QHBoxLayout(logs_group)
    window.view_logs_btn = QPushButton("Открыть логи")
    window.clear_logs_btn = QPushButton("Очистить логи")
    window.clear_logs_btn.setObjectName("warningButton")
    logs_layout.addWidget(window.view_logs_btn)
    logs_layout.addWidget(window.clear_logs_btn)
    layout.addWidget(logs_group)

    layout.addStretch()
    window.tabs.addTab(tab, "Логи")
