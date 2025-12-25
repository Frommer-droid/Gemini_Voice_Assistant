# -*- coding: utf-8 -*-
"""Вкладка системных настроек."""

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


def create_system_tab(window) -> None:
    tab = QWidget()
    layout = QVBoxLayout(tab)

    autostart_group = QGroupBox("Автозагрузка")
    autostart_layout = QVBoxLayout(autostart_group)
    window.autostart_check = QCheckBox("Запускать вместе с Windows")
    window.autostart_check.setChecked(
        window.assistant.settings.get("autostart_enabled")
    )
    window.start_minimized_check = QCheckBox("Запускать свернутым в трей")
    window.start_minimized_check.setChecked(
        window.assistant.settings.get("start_minimized")
    )
    autostart_layout.addWidget(window.autostart_check)
    autostart_layout.addWidget(window.start_minimized_check)
    layout.addWidget(autostart_group)

    wizard_group = QGroupBox("Первый запуск")
    wizard_layout = QVBoxLayout(wizard_group)
    wizard_info = QLabel(
        "Повторно запустите мастер для настройки API, VPN и Everything."
    )
    wizard_info.setWordWrap(True)
    wizard_layout.addWidget(wizard_info)
    window.first_run_btn = QPushButton("Запустить мастер заново")
    wizard_layout.addWidget(window.first_run_btn)
    layout.addWidget(wizard_group)

    layout.addStretch()
    window.tabs.addTab(tab, "Система")
