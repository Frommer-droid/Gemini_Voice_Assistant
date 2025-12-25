# -*- coding: utf-8 -*-
"""Вкладка истории."""

from PySide6.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def create_history_tab(window) -> None:
    tab = QWidget()
    layout = QVBoxLayout(tab)

    size_group = QGroupBox("Окно истории")
    size_layout = QVBoxLayout(size_group)
    width_layout = QHBoxLayout()
    width_layout.addWidget(QLabel("Ширина:"))
    window.history_width_spin = QSpinBox()
    window.history_width_spin.setRange(300, 1200)
    window.history_width_spin.setValue(
        window.assistant.settings.get("history_window_width")
    )
    width_layout.addWidget(window.history_width_spin)
    size_layout.addLayout(width_layout)

    height_layout = QHBoxLayout()
    height_layout.addWidget(QLabel("Высота:"))
    window.history_height_spin = QSpinBox()
    window.history_height_spin.setRange(200, 1000)
    window.history_height_spin.setValue(
        window.assistant.settings.get("history_window_height")
    )
    height_layout.addWidget(window.history_height_spin)
    size_layout.addLayout(height_layout)

    font_layout = QHBoxLayout()
    font_layout.addWidget(QLabel("Размер шрифта:"))
    window.history_font_spin = QSpinBox()
    window.history_font_spin.setRange(6, 20)
    window.history_font_spin.setValue(
        window.assistant.settings.get("history_font_size", 10)
    )
    font_layout.addWidget(window.history_font_spin)
    size_layout.addLayout(font_layout)

    layout.addWidget(size_group)

    history_group = QGroupBox("История записей")
    history_layout = QVBoxLayout(history_group)
    window.history_combo = QComboBox()
    history_layout.addWidget(window.history_combo)

    history_buttons_layout = QHBoxLayout()
    window.view_history_btn = QPushButton("Открыть запись")
    window.open_history_file_btn = QPushButton("Открыть файл истории")
    window.clear_history_btn = QPushButton("Очистить историю")
    window.clear_history_btn.setObjectName("warningButton")
    history_buttons_layout.addWidget(window.view_history_btn)
    history_buttons_layout.addWidget(window.open_history_file_btn)
    history_buttons_layout.addWidget(window.clear_history_btn)
    history_layout.addLayout(history_buttons_layout)
    layout.addWidget(history_group)

    window.update_history_combo()

    layout.addStretch()
    window.tabs.addTab(tab, "История")
