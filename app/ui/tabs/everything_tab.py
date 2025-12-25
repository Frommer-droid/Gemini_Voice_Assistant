# -*- coding: utf-8 -*-
"""Вкладка поиска Everything."""

import os

from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.app_config import EXE_DIR


def create_everything_tab(window) -> None:
    tab = QWidget()
    layout = QVBoxLayout(tab)

    search_group = QGroupBox("Поиск Everything")
    search_layout = QVBoxLayout(search_group)

    info_label = QLabel(
        "Поиск всегда использует папку _internal/Everything рядом с приложением."
    )
    info_label.setWordWrap(True)
    search_layout.addWidget(info_label)

    path_layout = QHBoxLayout()
    window.everything_dir_edit = QLineEdit()
    internal_dir = os.path.normpath(os.path.join(EXE_DIR, "_internal", "Everything"))
    window.everything_dir_edit.setText(internal_dir)
    window.everything_dir_edit.setReadOnly(True)
    window.everything_dir_edit.setToolTip("Путь фиксирован и не настраивается.")
    path_layout.addWidget(window.everything_dir_edit, 1)
    search_layout.addLayout(path_layout)

    hint_label = QLabel("Выбор другой папки отключен.")
    hint_label.setWordWrap(True)
    search_layout.addWidget(hint_label)

    actions_layout = QHBoxLayout()
    window.everything_check_btn = QPushButton("Проверить/Запустить")
    actions_layout.addWidget(window.everything_check_btn)
    actions_layout.addStretch()
    search_layout.addLayout(actions_layout)

    window.everything_status_label = QLabel("Статус: неизвестно")
    window.everything_status_label.setWordWrap(True)
    search_layout.addWidget(window.everything_status_label)

    layout.addWidget(search_group)
    layout.addStretch()
    window.tabs.addTab(tab, "Поиск")
    window.everything_check_btn.clicked.connect(window.on_everything_check)
    window._refresh_everything_status(startup_check=False)
