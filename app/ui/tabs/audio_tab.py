# -*- coding: utf-8 -*-
"""Вкладка аудио."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.audio.audio_utils import get_microphone_list
from app.ui.ui_dialogs import NoElidingDelegate


def create_audio_tab(window) -> None:
    tab = QWidget()
    layout = QVBoxLayout(tab)

    mic_group = QGroupBox("Микрофон")
    mic_layout = QVBoxLayout(mic_group)
    mic_controls_layout = QHBoxLayout()

    window.mic_combo = QComboBox()
    window.mic_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
    window.mic_combo.setMinimumWidth(500)
    window.mic_combo.setMaxVisibleItems(10)

    # Применяем кастомный делегат для показа полного текста
    window.mic_combo.setItemDelegate(NoElidingDelegate(window.mic_combo))

    # Заполнение списка
    window.mic_combo.addItem("По умолчанию (системный)", None)
    for i, name in get_microphone_list():
        window.mic_combo.addItem(name, i)
        index = window.mic_combo.count() - 1
        window.mic_combo.setItemData(index, name, Qt.ItemDataRole.ToolTipRole)

    # Настройка view для показа полного текста
    view = window.mic_combo.view()
    view.setTextElideMode(Qt.TextElideMode.ElideRight)
    view.setResizeMode(view.ResizeMode.Adjust)

    # Принудительное обновление размеров
    window.mic_combo.updateGeometry()
    view.updateGeometry()

    # Восстановление выбранного
    saved_index = window.assistant.settings.get("microphone_index")
    if saved_index is None:
        window.mic_combo.setCurrentIndex(0)
    else:
        combo_index = window.mic_combo.findData(saved_index)
        if combo_index != -1:
            window.mic_combo.setCurrentIndex(combo_index)
        else:
            window.mic_combo.setCurrentIndex(0)

    mic_controls_layout.addWidget(window.mic_combo, 1)

    window.refresh_mic_btn = QPushButton("??")
    window.refresh_mic_btn.setFixedWidth(40)
    window.refresh_mic_btn.setToolTip("Обновить список")
    mic_controls_layout.addWidget(window.refresh_mic_btn)
    window.refresh_mic_btn.clicked.connect(window.refresh_microphone_list)

    mic_layout.addLayout(mic_controls_layout)
    layout.addWidget(mic_group)

    sound_group = QGroupBox("Звуковая схема")
    sound_layout = QHBoxLayout(sound_group)
    window.sound_combo = QComboBox()
    window.sound_combo.addItems(["Стандартные", "Тихие", "Мелодичные", "Отключены"])
    window.sound_combo.setCurrentText(window.assistant.settings.get("sound_scheme"))
    sound_layout.addWidget(window.sound_combo)
    layout.addWidget(sound_group)

    quality_group = QGroupBox("Качество записи")
    quality_layout = QVBoxLayout(quality_group)
    window.quality_check = QCheckBox("Silence guard")
    window.quality_check.setChecked(
        window.assistant.settings.get("silence_detection_enabled")
    )
    quality_layout.addWidget(window.quality_check)

    min_level_layout = QHBoxLayout()
    min_level_layout.addWidget(QLabel("Min level:"))
    window.min_level_spin = QSpinBox()
    window.min_level_spin.setRange(100, 5000)
    window.min_level_spin.setValue(window.assistant.settings.get("min_audio_level"))
    min_level_layout.addWidget(window.min_level_spin)
    quality_layout.addLayout(min_level_layout)

    silence_duration_layout = QHBoxLayout()
    silence_duration_layout.addWidget(QLabel("Min duration (ms):"))
    window.silence_duration_spin = QSpinBox()
    window.silence_duration_spin.setRange(100, 5000)
    window.silence_duration_spin.setSingleStep(50)
    window.silence_duration_spin.setValue(
        window.assistant.settings.get("silence_duration_ms")
    )
    silence_duration_layout.addWidget(window.silence_duration_spin)
    quality_layout.addLayout(silence_duration_layout)

    window.vad_check = QCheckBox("Faster-Whisper VAD")
    window.vad_check.setChecked(
        window.assistant.settings.get("whisper_vad_enabled")
    )
    quality_layout.addWidget(window.vad_check)

    thresholds_layout = QHBoxLayout()
    thresholds_layout.addWidget(QLabel("no_speech:"))
    window.no_speech_spin = QDoubleSpinBox()
    window.no_speech_spin.setRange(0.0, 1.0)
    window.no_speech_spin.setDecimals(2)
    window.no_speech_spin.setSingleStep(0.01)
    window.no_speech_spin.setValue(
        window.assistant.settings.get("no_speech_threshold")
    )
    thresholds_layout.addWidget(window.no_speech_spin)
    thresholds_layout.addWidget(QLabel("logprob:"))
    window.logprob_spin = QDoubleSpinBox()
    window.logprob_spin.setRange(-5.0, 0.0)
    window.logprob_spin.setDecimals(2)
    window.logprob_spin.setSingleStep(0.05)
    window.logprob_spin.setValue(
        window.assistant.settings.get("logprob_threshold")
    )
    thresholds_layout.addWidget(window.logprob_spin)
    quality_layout.addLayout(thresholds_layout)

    window.condition_check = QCheckBox("Keep Whisper context")
    window.condition_check.setChecked(
        window.assistant.settings.get("condition_on_prev_text")
    )
    quality_layout.addWidget(window.condition_check)

    layout.addWidget(quality_group)

    layout.addStretch()
    window.tabs.addTab(tab, "Аудио")
