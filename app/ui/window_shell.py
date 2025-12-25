# -*- coding: utf-8 -*-
"""Создание каркаса окна: виджеты и компоновка."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QLabel,
    QProgressBar,
    QSizeGrip,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
)

from app.core.app_config import APP_VERSION


def create_window_widgets(window) -> None:
    window.central_widget = QFrame()
    window.central_widget.setObjectName("centralWidget")
    window.setCentralWidget(window.central_widget)

    window.title_label = QLabel(f"Gemini Voice Assistant v{APP_VERSION}")
    window.title_label.setObjectName("titleLabel")
    window.status_label = QLabel("Готов к работе")
    window.status_label.setObjectName("statusLabel")

    window.bottom_bar = QFrame()
    window.bottom_bar.setObjectName("bottomBar")

    window.work_indicator = QProgressBar()
    window.work_indicator.setRange(0, 0)
    window.work_indicator.setTextVisible(False)
    window.work_indicator.setFixedHeight(8)
    window.work_indicator.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    window.work_indicator.setVisible(False)

    window.volume_indicator = QProgressBar()
    window.volume_indicator.setRange(0, 100)
    window.volume_indicator.setValue(0)
    window.volume_indicator.setTextVisible(False)
    window.volume_indicator.setFixedHeight(8)
    window.volume_indicator.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )

    window.toggle_settings_button = QPushButton("▼")
    window.toggle_settings_button.setObjectName("toggleButton")
    window.toggle_settings_button.setFixedSize(24, 24)
    window.toggle_settings_button.setFlat(True)
    window.toggle_settings_button.installEventFilter(window)

    window.hide_to_tray_button = QPushButton("▶")
    window.hide_to_tray_button.setObjectName("hideButton")
    window.hide_to_tray_button.setFixedSize(24, 24)
    window.hide_to_tray_button.setToolTip("Скрыть в трей")
    window.hide_to_tray_button.setFlat(True)

    window.size_grip = QSizeGrip(window.central_widget)
    window.size_grip.setFixedSize(16, 16)

    window.settings_panel = QFrame()
    window.settings_panel.setObjectName("settingsPanel")
    window.settings_panel.setVisible(False)

    window.settings_layout = QVBoxLayout(window.settings_panel)
    window.tabs = QTabWidget()
    window.settings_layout.addWidget(window.tabs)

    window.create_main_tab()
    window.create_audio_tab()
    window.create_ui_tab()
    window.create_history_tab()
    window.create_logs_tab()
    window.create_system_tab()
    window.create_everything_tab()
    # VPN вкладка
    vpn_tab = window.create_vpn_tab()
    window.tabs.addTab(vpn_tab, "VPN")
    # Обновление статуса VPN после автозапуска
    if (
        hasattr(window.assistant, "vless_manager")
        and window.assistant.vless_manager.is_running
    ):
        QTimer.singleShot(500, window.update_vpn_status)

    window.create_gemini_tab_v2()
    window._install_autofit_watchers()


def create_window_layout(window) -> None:
    window.main_layout = QVBoxLayout(window.central_widget)
    window.main_layout.setContentsMargins(20, 15, 20, 15)
    window.main_layout.setSpacing(10)

    window.top_bar_layout = QHBoxLayout()
    window.top_bar_layout.setContentsMargins(0, 0, 0, 0)
    window.top_bar_layout.setSpacing(10)

    window.top_bar_layout.addWidget(
        window.hide_to_tray_button, 0, Qt.AlignmentFlag.AlignLeft
    )
    window.top_bar_layout.addWidget(
        window.title_label, 1, Qt.AlignmentFlag.AlignCenter
    )
    window.top_bar_layout.addWidget(
        window.toggle_settings_button, 0, Qt.AlignmentFlag.AlignRight
    )

    window.main_layout.addLayout(window.top_bar_layout)
    window.main_layout.addWidget(
        window.status_label, alignment=Qt.AlignmentFlag.AlignCenter
    )

    bottom_bar_layout = QHBoxLayout(window.bottom_bar)
    bottom_bar_layout.setContentsMargins(0, 0, 0, 0)
    bottom_bar_layout.setSpacing(10)

    indicators_container = QFrame()
    indicators_layout = QVBoxLayout(indicators_container)
    indicators_layout.setSpacing(5)
    indicators_layout.setContentsMargins(0, 0, 0, 0)
    indicators_layout.addWidget(window.work_indicator)
    indicators_layout.addWidget(window.volume_indicator)

    indicators_container.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )

    bottom_bar_layout.addWidget(indicators_container, 1)

    window.main_layout.addWidget(window.bottom_bar)
    window.main_layout.addWidget(window.settings_panel)
    window.main_layout.addStretch()
