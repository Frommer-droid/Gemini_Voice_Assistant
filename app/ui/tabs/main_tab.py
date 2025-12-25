# -*- coding: utf-8 -*-
"""Вкладка основных настроек."""

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)


def create_main_tab(window) -> None:
    tab = QWidget()
    layout = QVBoxLayout(tab)

    whisper_group = QGroupBox("Whisper")
    whisper_layout = QHBoxLayout(whisper_group)
    window.whisper_combo = QComboBox()
    # ИЗМЕНЕНО: только small и medium
    window.whisper_combo.addItems(["small", "medium"])
    window.whisper_combo.setCurrentText(
        window.assistant.settings.get("whisper_model")
    )
    window.whisper_combo.setMinimumContentsLength(10)

    # УДАЛЕНО: window.download_model_btn = QPushButton("Загрузить")

    whisper_layout.addWidget(window.whisper_combo)
    # УДАЛЕНО: whisper_layout.addWidget(window.download_model_btn)
    layout.addWidget(whisper_group)

    gemini_group = QGroupBox("Gemini")
    gemini_layout = QVBoxLayout(gemini_group)

    # --- Gemini 3.0 Pro ---
    g3_pro_group = QGroupBox("Gemini 3.0 Pro")
    g3_pro_layout = QHBoxLayout(g3_pro_group)
    window.g3_pro_high_check = QCheckBox("High")
    window.g3_pro_low_check = QCheckBox("Low")
    g3_pro_layout.addWidget(window.g3_pro_high_check)
    g3_pro_layout.addWidget(window.g3_pro_low_check)

    g3_pro_level = (
        window.assistant.settings.get("gemini3_pro_thinking_level") or "high"
    ).lower()
    window.g3_pro_high_check.setChecked(g3_pro_level == "high")
    window.g3_pro_low_check.setChecked(g3_pro_level == "low")
    if not (
        window.g3_pro_high_check.isChecked()
        or window.g3_pro_low_check.isChecked()
    ):
        window.g3_pro_high_check.setChecked(True)

    gemini_layout.addWidget(g3_pro_group)

    # --- Gemini 3.0 Flash ---
    g3_flash_group = QGroupBox("Gemini 3.0 Flash")
    g3_flash_layout = QHBoxLayout(g3_flash_group)

    window.g3_flash_group_bg = QButtonGroup(window)

    window.g3_flash_high_radio = QRadioButton("High")
    window.g3_flash_medium_radio = QRadioButton("Medium")
    window.g3_flash_low_radio = QRadioButton("Low")
    window.g3_flash_minimal_radio = QRadioButton("Minimal")

    window.g3_flash_group_bg.addButton(window.g3_flash_high_radio, 1)
    window.g3_flash_group_bg.addButton(window.g3_flash_medium_radio, 2)
    window.g3_flash_group_bg.addButton(window.g3_flash_low_radio, 3)
    window.g3_flash_group_bg.addButton(window.g3_flash_minimal_radio, 4)

    g3_flash_layout.addWidget(window.g3_flash_high_radio)
    g3_flash_layout.addWidget(window.g3_flash_medium_radio)
    g3_flash_layout.addWidget(window.g3_flash_low_radio)
    g3_flash_layout.addWidget(window.g3_flash_minimal_radio)

    g3_flash_level = (
        window.assistant.settings.get("gemini3_flash_thinking_level") or "high"
    ).lower()

    if g3_flash_level == "high":
        window.g3_flash_high_radio.setChecked(True)
    elif g3_flash_level == "medium":
        window.g3_flash_medium_radio.setChecked(True)
    elif g3_flash_level == "low":
        window.g3_flash_low_radio.setChecked(True)
    elif g3_flash_level == "minimal":
        window.g3_flash_minimal_radio.setChecked(True)
    else:
        window.g3_flash_high_radio.setChecked(True)

    gemini_layout.addWidget(g3_flash_group)

    layout.addWidget(gemini_group)

    # Подключаем сигналы здесь, чтобы сохранить прежнюю логику.
    window.g3_pro_high_check.toggled.connect(window.on_g3_pro_high_changed)
    window.g3_pro_low_check.toggled.connect(window.on_g3_pro_low_changed)

    window.g3_flash_group_bg.buttonClicked.connect(window.on_g3_flash_level_changed)

    proxy_group = QGroupBox("Прокси")
    proxy_layout = QVBoxLayout(proxy_group)
    window.proxy_check = QCheckBox("Использовать прокси")
    window.proxy_check.setChecked(window.assistant.settings.get("proxy_enabled"))
    proxy_layout.addWidget(window.proxy_check)

    proxy_addr_layout = QHBoxLayout()
    proxy_addr_layout.addWidget(QLabel("Адрес:"))
    window.proxy_addr_edit = QLineEdit()
    window.proxy_addr_edit.setText(window.assistant.settings.get("proxy_address"))
    proxy_addr_layout.addWidget(window.proxy_addr_edit)
    proxy_layout.addLayout(proxy_addr_layout)

    proxy_port_layout = QHBoxLayout()
    proxy_port_layout.addWidget(QLabel("Порт:"))
    window.proxy_port_edit = QLineEdit()
    window.proxy_port_edit.setText(
        str(window.assistant.settings.get("proxy_port"))
    )
    proxy_port_layout.addWidget(window.proxy_port_edit)
    proxy_layout.addLayout(proxy_port_layout)
    layout.addWidget(proxy_group)

    # Подсказка о приоритете VPN/Proxy
    proxy_hint = QLabel(
        "Если включён VLESS на вкладке <VPN> - будет использован он.\n"
        "Если VLESS выключен, используется этот прокси (например, v2rayN)."
    )
    proxy_hint.setStyleSheet("color: #9AA7B0; font-size: 11px;")
    layout.addWidget(proxy_hint)

    hotkey_group = QGroupBox("Режимы горячих клавиш")
    hotkey_layout = QHBoxLayout(hotkey_group)

    win_shift_group = QGroupBox("Режим удержания")
    win_shift_layout = QVBoxLayout(win_shift_group)
    window.win_shift_normal = QRadioButton("Обычный")
    window.win_shift_continuous = QRadioButton("Непрерывный")
    window.win_shift_normal.setChecked(
        window.assistant.settings.get("win_shift_mode") == "Обычный"
    )
    window.win_shift_continuous.setChecked(
        window.assistant.settings.get("win_shift_mode") == "Непрерывный"
    )
    win_shift_layout.addWidget(window.win_shift_normal)
    win_shift_layout.addWidget(window.win_shift_continuous)
    hotkey_layout.addWidget(win_shift_group)
    hold_group = QGroupBox("Сочетание удержания")
    hold_layout = QVBoxLayout(hold_group)
    window.hold_win_shift = QRadioButton("Левый Win + левый Shift (по умолчанию)")
    window.hold_ctrl_shift = QRadioButton("Левый Ctrl + левый Shift")
    current_hold = (
        window.assistant.settings.get("hold_hotkey") or "win+shift"
    ).lower()
    window.hold_win_shift.setChecked(current_hold == "win+shift")
    window.hold_ctrl_shift.setChecked(current_hold == "ctrl+shift")
    for btn in [
        window.hold_win_shift,
        window.hold_ctrl_shift,
    ]:
        hold_layout.addWidget(btn)
    hotkey_layout.addWidget(hold_group)

    f1_group = QGroupBox("F1")
    f1_layout = QVBoxLayout(f1_group)
    window.f1_normal = QRadioButton("Обычный")
    window.f1_continuous = QRadioButton("Непрерывный")
    window.f1_normal.setChecked(
        window.assistant.settings.get("f1_mode") == "Обычный"
    )
    window.f1_continuous.setChecked(
        window.assistant.settings.get("f1_mode") == "Непрерывный"
    )
    f1_layout.addWidget(window.f1_normal)
    f1_layout.addWidget(window.f1_continuous)
    hotkey_layout.addWidget(f1_group)
    layout.addWidget(hotkey_group)

    layout.addStretch()
    window.tabs.addTab(tab, "Основные")
