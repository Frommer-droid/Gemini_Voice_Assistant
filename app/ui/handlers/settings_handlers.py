# -*- coding: utf-8 -*-
"""Обработчики настроек и аудио."""

import threading
import traceback

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.audio.audio_utils import get_microphone_list
from app.core.app_config import COLORS
from app.core.settings_store import normalize_hold_hotkey
from app.ui import window_behavior
from app.ui.ui_dialogs import NoElidingDelegate
from app.utils.logging_utils import log_message


def on_selection_word_changed(window) -> None:
    window.assistant.save_setting("selection_word", window.selection_word_edit.text())
    window.assistant.show_status(
        "Слово для выделения сохранено", COLORS["accent"], False
    )


def on_pro_word_changed(window) -> None:
    window.assistant.save_setting("pro_word", window.pro_word_edit.text())
    window.assistant.show_status(
        "Слово для Pro-модели сохранено", COLORS["accent"], False
    )


def on_flash_word_changed(window) -> None:
    window.assistant.save_setting("flash_word", window.flash_word_edit.text())
    window.assistant.show_status(
        "Слово для Flash-модели сохранено", COLORS["accent"], False
    )


def on_model_changed(window) -> None:
    model_name = window.whisper_combo.currentText()
    window.assistant.save_setting("whisper_model", model_name)

    log_message(f"Выбрана модель {model_name}, запускаем активацию...")
    window.assistant.show_status(f"Активация {model_name}...", COLORS["accent"], True)

    threading.Thread(
        target=window.assistant.setup_whisper, args=(model_name,), daemon=True
    ).start()


def on_autostart_changed(window, state) -> None:
    enabled = bool(state)
    window.assistant.save_setting("autostart_enabled", enabled)
    window.assistant.set_autostart(enabled)
    status = "включена" if enabled else "выключена"
    window.assistant.show_status(f"Автозагрузка {status}", COLORS["accent"], False)


def on_start_minimized_changed(window, state) -> None:
    enabled = bool(state)
    window.assistant.save_setting("start_minimized", enabled)
    status = "включен" if enabled else "выключен"
    window.assistant.show_status(
        f"Запуск свернутым {status}", COLORS["accent"], False
    )


def on_win_shift_mode_changed(window) -> None:
    if window.win_shift_normal.isChecked():
        window.assistant.save_setting("win_shift_mode", "Обычный")
        window.assistant.show_status(
            "Win+Shift: Обычный режим", COLORS["accent"], False
        )
    else:
        window.assistant.save_setting("win_shift_mode", "Непрерывный")
        window.assistant.show_status(
            "Win+Shift: Непрерывный режим", COLORS["accent"], False
        )


def on_hold_hotkey_changed(window, value) -> None:
    normalized = normalize_hold_hotkey(value)
    window.assistant.save_setting("hold_hotkey", normalized)
    window.assistant.update_hotkey_combo(normalized)
    window.assistant.show_status(f"Удержание: {normalized}", COLORS["accent"], False)


def on_f1_mode_changed(window) -> None:
    if window.f1_normal.isChecked():
        window.assistant.save_setting("f1_mode", "Обычный")
        window.assistant.show_status("F1: Обычный режим", COLORS["accent"], False)
    else:
        window.assistant.save_setting("f1_mode", "Непрерывный")
        window.assistant.show_status("F1: Непрерывный режим", COLORS["accent"], False)


def on_mic_changed(window, index) -> None:
    selected_index = window.mic_combo.currentData()
    window.assistant.save_setting("microphone_index", selected_index)

    mic_name = window.mic_combo.currentText()
    log_message(f"Выбран микрофон: {mic_name} (индекс: {selected_index})")

    window.assistant.show_status(f"Микрофон: {mic_name}", COLORS["accent"], False)


def on_sound_scheme_changed(window, scheme) -> None:
    window.assistant.save_setting("sound_scheme", scheme)
    window.assistant.show_status(f"Звуковая схема: {scheme}", COLORS["accent"], False)


def on_quality_check_changed(window, state) -> None:
    enabled = bool(state)
    window.assistant.save_setting("audio_quality_check", enabled)
    window.assistant.save_setting("silence_detection_enabled", enabled)
    status = "включено" if enabled else "выключено"
    window.assistant.show_status(
        f"Предупреждение о тишине {status}", COLORS["accent"], False
    )


def on_min_level_changed(window, value) -> None:
    window.assistant.save_setting("min_audio_level", value)
    window.assistant.show_status(f"Мин. уровень: {value}", COLORS["accent"], False)


def on_silence_duration_changed(window, value) -> None:
    window.assistant.save_setting("silence_duration_ms", value)
    window.assistant.show_status(
        "Min duration: {} ms".format(value), COLORS["accent"], False
    )


def on_vad_changed(window, state) -> None:
    enabled = bool(state)
    window.assistant.save_setting("whisper_vad_enabled", enabled)
    status = "enabled" if enabled else "disabled"
    window.assistant.show_status(f"VAD Whisper {status}", COLORS["accent"], False)


def on_no_speech_changed(window, value) -> None:
    value = float(value)
    window.assistant.save_setting("no_speech_threshold", value)
    window.assistant.show_status(f"no_speech = {value:.2f}", COLORS["accent"], False)


def on_logprob_changed(window, value) -> None:
    value = float(value)
    window.assistant.save_setting("logprob_threshold", value)
    window.assistant.show_status(f"logprob = {value:.2f}", COLORS["accent"], False)


def on_condition_prev_changed(window, state) -> None:
    enabled = bool(state)
    window.assistant.save_setting("condition_on_prev_text", enabled)
    status = "enabled" if enabled else "disabled"
    window.assistant.show_status(f"Context Whisper {status}", COLORS["accent"], False)


def on_size_setting_changed(window, key, value) -> None:
    window.assistant.save_setting(key, value)
    window.assistant.show_status(
        f"Настройка '{key}' сохранена: {value}", COLORS["accent"], False
    )


def apply_font_settings(window) -> None:
    window.assistant.save_setting("title_font_size", window.title_font_spin.value())
    window.assistant.save_setting("status_font_size", window.status_font_spin.value())
    update_label_fonts(window)


def update_label_fonts(window) -> None:
    title_size = window.assistant.settings.get("title_font_size")
    status_size = window.assistant.settings.get("status_font_size")
    window.title_label.setStyleSheet(
        f"color: {COLORS['white']}; font-size: {title_size}pt; font-weight: bold;"
    )
    window.status_label.setStyleSheet(
        f"color: {COLORS['accent']}; font-size: {status_size}pt;"
    )


def apply_ui_settings(window) -> None:
    update_label_fonts(window)
    width = window.assistant.settings.get("compact_width")
    height = window.assistant.settings.get("compact_height")
    adjusted_width, min_width = window_behavior.apply_width_floor(
        window, width, "compact"
    )
    adjusted_height, min_height = window_behavior.apply_height_floor(
        window, height, "compact"
    )
    if adjusted_width != width:
        window_behavior.sync_size_setting(
            window, "compact_width", adjusted_width, "compact_width_spin"
        )
        log_message(
            f"Автоподбор ширины компактного режима: {width} -> {adjusted_width}"
        )
    if adjusted_height != height:
        window_behavior.sync_size_setting(
            window, "compact_height", adjusted_height, "compact_height_spin"
        )
        log_message(
            "Автоподбор высоты компактного режима: "
            f"{height} -> {adjusted_height}"
        )
    window.is_programmatic_resize = True
    window.resize(adjusted_width, adjusted_height)
    window.is_programmatic_resize = False
    window.setMinimumSize(min_width, min_height)
    log_message("Настройки интерфейса применены.")


def refresh_microphone_list(window) -> None:
    """
    Перезапрашивает устройства и полностью обновляет содержимое комбобокса.
    ИСПРАВЛЕННАЯ ВЕРСИЯ с полной переинициализацией!
    """
    log_message("=" * 60)
    log_message("НАЧАЛО ОБНОВЛЕНИЯ СПИСКА МИКРОФОНОВ")

    current_index = window.mic_combo.currentData()
    log_message(f"Текущий выбранный индекс: {current_index}")

    window.mic_combo.blockSignals(True)

    try:
        window.mic_combo.clear()
        log_message("Комбобокс очищен")

        import sounddevice as sd

        try:
            sd._terminate()
            sd._initialize()
            log_message("Кэш sounddevice сброшен")
        except Exception:
            log_message("Не удалось сбросить кэш sounddevice (не критично)")

        microphones = get_microphone_list()
        log_message(f"Получено устройств: {len(microphones)}")

        window.mic_combo.addItem("По умолчанию (системный)", None)
        log_message("Добавлен пункт 'По умолчанию'")

        for i, name in microphones:
            window.mic_combo.addItem(name, i)
            combo_idx = window.mic_combo.count() - 1
            window.mic_combo.setItemData(
                combo_idx,
                f"Индекс: {i}, Имя: {name}",
                Qt.ItemDataRole.ToolTipRole,
            )
            log_message(f"  [{combo_idx}] Добавлен: '{name}' (device_idx={i})")

        window.mic_combo.setItemDelegate(NoElidingDelegate(window.mic_combo))
        view = window.mic_combo.view()
        view.setTextElideMode(Qt.TextElideMode.ElideRight)
        view.setResizeMode(view.ResizeMode.Adjust)
        window.mic_combo.updateGeometry()
        view.updateGeometry()

        if current_index is not None:
            combo_index = window.mic_combo.findData(current_index)
            if combo_index != -1:
                window.mic_combo.setCurrentIndex(combo_index)
                log_message(
                    f"Восстановлен выбор: индекс {current_index} (позиция {combo_index})"
                )
            else:
                window.mic_combo.setCurrentIndex(0)
                log_message(
                    f"Предыдущий микрофон (индекс {current_index}) не найден - выбран 'По умолчанию'"
                )
        else:
            window.mic_combo.setCurrentIndex(0)
            log_message("Выбран 'По умолчанию' (предыдущий выбор был None)")

    except Exception as e:
        log_message(f"ОШИБКА при обновлении списка микрофонов: {e}")
        log_message(traceback.format_exc())

    finally:
        window.mic_combo.blockSignals(False)

    window.mic_combo.repaint()
    QApplication.processEvents()

    window.assistant.show_status(
        f"Список обновлен: {len(microphones)} мик.", COLORS["accent"], False
    )

    log_message(
        f"Обновление завершено. Всего в списке: {window.mic_combo.count()} элементов"
    )
    log_message("=" * 60)
