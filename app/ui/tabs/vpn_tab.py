# -*- coding: utf-8 -*-
"""Вкладка VPN настроек."""

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)


def create_vpn_tab(window) -> QWidget:
    """Создание вкладки VPN настроек."""
    tab = QWidget()
    layout = QVBoxLayout(tab)

    # Включение VLESS
    vless_group = QGroupBox("VLESS VPN")
    vless_layout = QVBoxLayout(vless_group)

    window.vless_enabled_check = QCheckBox("Использовать VLESS VPN")
    window.vless_enabled_check.setChecked(
        window.assistant.settings.get("vless_enabled", False)
    )
    vless_layout.addWidget(window.vless_enabled_check)

    # VLESS URL
    vless_layout.addWidget(QLabel("VLESS URL:"))
    window.vless_url_edit = QLineEdit()
    window.vless_url_edit.setText(window.assistant.settings.get("vless_url", ""))
    window.vless_url_edit.setPlaceholderText("vless://uuid@server:port?...")
    vless_layout.addWidget(window.vless_url_edit)

    # ====== НОВОЕ: Порт SOCKS5 ======
    port_layout = QHBoxLayout()
    port_layout.addWidget(QLabel("Порт SOCKS5:"))
    window.vless_port_spin = QSpinBox()
    window.vless_port_spin.setRange(1024, 65535)
    window.vless_port_spin.setValue(
        window.assistant.settings.get("vless_port", 10809)
    )
    port_layout.addWidget(window.vless_port_spin)
    vless_layout.addLayout(port_layout)
    # ==============================

    # Автозапуск
    window.vless_autostart_check = QCheckBox("Автоматически подключаться при запуске")
    window.vless_autostart_check.setChecked(
        window.assistant.settings.get("vless_autostart", False)
    )
    vless_layout.addWidget(window.vless_autostart_check)

    layout.addWidget(vless_group)

    # Кнопки управления
    control_group = QGroupBox("Управление")
    control_layout = QHBoxLayout(control_group)

    window.vless_connect_btn = QPushButton("Подключить")
    window.vless_disconnect_btn = QPushButton("Отключить")
    window.vless_test_btn = QPushButton("Тест")

    window.vless_connect_btn.clicked.connect(window.vless_connect)
    window.vless_disconnect_btn.clicked.connect(window.vless_disconnect)
    window.vless_test_btn.clicked.connect(window.vless_test)

    control_layout.addWidget(window.vless_connect_btn)
    control_layout.addWidget(window.vless_disconnect_btn)
    control_layout.addWidget(window.vless_test_btn)

    layout.addWidget(control_group)

    # Статус
    window.vless_status_label = QLabel("Статус: не подключено")
    layout.addWidget(window.vless_status_label)

    layout.addStretch()

    # Подключаем сигналы для сохранения настроек
    window.vless_enabled_check.stateChanged.connect(window.on_vless_enabled_changed)
    window.vless_url_edit.editingFinished.connect(window.on_vless_url_changed)
    window.vless_port_spin.valueChanged.connect(window.on_vless_port_changed)
    window.vless_autostart_check.stateChanged.connect(window.on_vless_autostart_changed)

    return tab
