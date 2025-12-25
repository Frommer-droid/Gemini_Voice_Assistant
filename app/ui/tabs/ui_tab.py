# -*- coding: utf-8 -*-
"""Вкладка настроек интерфейса."""

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def create_ui_tab(window) -> None:
    tab = QWidget()
    layout = QVBoxLayout(tab)

    compact_group = QGroupBox("Компактный режим")
    compact_layout = QVBoxLayout(compact_group)

    compact_width_layout = QHBoxLayout()
    compact_width_layout.addWidget(QLabel("Ширина:"))
    window.compact_width_spin = QSpinBox()
    window.compact_width_spin.setRange(250, 1000)
    window.compact_width_spin.setValue(window.assistant.settings.get("compact_width"))
    compact_width_layout.addWidget(window.compact_width_spin)
    compact_layout.addLayout(compact_width_layout)

    compact_height_layout = QHBoxLayout()
    compact_height_layout.addWidget(QLabel("Высота:"))
    window.compact_height_spin = QSpinBox()
    window.compact_height_spin.setRange(100, 300)
    window.compact_height_spin.setValue(window.assistant.settings.get("compact_height"))
    compact_height_layout.addWidget(window.compact_height_spin)
    compact_layout.addLayout(compact_height_layout)
    layout.addWidget(compact_group)

    expanded_group = QGroupBox("Развернутый режим")
    expanded_layout = QVBoxLayout(expanded_group)

    expanded_width_layout = QHBoxLayout()
    expanded_width_layout.addWidget(QLabel("Ширина:"))
    window.expanded_width_spin = QSpinBox()
    window.expanded_width_spin.setRange(250, 1000)
    window.expanded_width_spin.setValue(window.assistant.settings.get("expanded_width"))
    expanded_width_layout.addWidget(window.expanded_width_spin)
    expanded_layout.addLayout(expanded_width_layout)

    expanded_height_layout = QHBoxLayout()
    expanded_height_layout.addWidget(QLabel("Высота:"))
    window.expanded_height_spin = QSpinBox()
    window.expanded_height_spin.setRange(300, 1200)
    window.expanded_height_spin.setValue(
        window.assistant.settings.get("expanded_height")
    )
    expanded_height_layout.addWidget(window.expanded_height_spin)
    expanded_layout.addLayout(expanded_height_layout)
    layout.addWidget(expanded_group)

    font_group = QGroupBox("Размеры шрифтов")
    font_layout = QVBoxLayout(font_group)

    title_layout = QHBoxLayout()
    title_layout.addWidget(QLabel("Заголовок:"))
    window.title_font_spin = QSpinBox()
    window.title_font_spin.setRange(10, 30)
    window.title_font_spin.setValue(window.assistant.settings.get("title_font_size"))
    title_layout.addWidget(window.title_font_spin)
    font_layout.addLayout(title_layout)

    status_layout = QHBoxLayout()
    status_layout.addWidget(QLabel("Статус:"))
    window.status_font_spin = QSpinBox()
    window.status_font_spin.setRange(8, 24)
    window.status_font_spin.setValue(window.assistant.settings.get("status_font_size"))
    status_layout.addWidget(window.status_font_spin)
    font_layout.addLayout(status_layout)
    layout.addWidget(font_group)

    layout.addStretch()
    window.tabs.addTab(tab, "Интерфейс")
