# -*- coding: utf-8 -*-
"""Главное окно и сигналы UI."""

from app.core.app_config import APP_VERSION, EXE_DIR
from app.ui.handlers import (
    everything_handlers,
    gemini_handlers,
    history_handlers,
    settings_handlers,
    vpn_handlers,
)
from app.ui import window_behavior
from app.ui.tabs.audio_tab import create_audio_tab as build_audio_tab
from app.ui.tabs.everything_tab import create_everything_tab as build_everything_tab
from app.ui.tabs.gemini_tabs import create_gemini_tab as build_gemini_tab
from app.ui.tabs.gemini_tabs import create_gemini_tab_v2 as build_gemini_tab_v2
from app.ui.tabs.history_tab import create_history_tab as build_history_tab
from app.ui.tabs.logs_tab import create_logs_tab as build_logs_tab
from app.ui.tabs.main_tab import create_main_tab as build_main_tab
from app.ui.tabs.system_tab import create_system_tab as build_system_tab
from app.ui.tabs.ui_tab import create_ui_tab as build_ui_tab
from app.ui.tabs.vpn_tab import create_vpn_tab as build_vpn_tab
from app.ui.tray import create_colored_icon as build_tray_colored_icon
from app.ui.tray import check_tray_visibility as build_tray_visibility
from app.ui.tray import create_tray_icon as build_tray_icon
from app.ui.tray import on_tray_activated as build_tray_activation
from app.ui.tray import toggle_pause as build_tray_pause
from app.ui.ui_dialogs import FirstRunWizard
from app.ui.window_shell import create_window_layout, create_window_widgets
from app.ui.window_signals import connect_window_signals
from app.utils.logging_utils import log_message

from PySide6.QtCore import Qt, QTimer, Signal, QObject, QRect, QPoint
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMainWindow

class UiSignals(QObject):
    status_changed = Signal(str, str, bool)
    volume_changed = Signal(int)
    recording_state_changed = Signal(bool)
    history_updated = Signal()
    request_show_window = Signal()
    request_hide_window = Signal()
    request_show_logs = Signal()
    request_refresh_everything = Signal()


class ModernWindow(QMainWindow):
    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant
        self.assistant.ui_signals = UiSignals()
        self.drag_pos = QPoint()
        self.is_resizing = False
        self.resize_edges = tuple()
        self.resize_origin = QPoint()
        self.initial_geometry = QRect()
        self.resize_margin = 12
        self.is_programmatic_resize = False

        self.setWindowTitle(f"Gemini Voice Assistant v{APP_VERSION}")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.settings_expanded = False
        self.log_viewer = None
        self.history_viewer = None

        self._create_widgets()
        self._create_layout()
        self._apply_styles()
        self._connect_signals()

        self.assistant.post_ui_init()

        self.apply_ui_settings()

        # ИСПРАВЛЕНО: Правильный порядок инициализации
        self.position_window()
        self.show()
        QApplication.processEvents()

        QTimer.singleShot(200, self._create_tray_icon)
        QTimer.singleShot(400, self.maybe_show_first_run_wizard)

        # Обновление статуса VPN после автозапуска
        if (
            hasattr(self.assistant, "vless_manager")
            and self.assistant.vless_manager.is_running
        ):
            QTimer.singleShot(500, self.update_vpn_status)

        if self.assistant.settings.get("start_minimized"):
            QTimer.singleShot(800, self.hide)

    def mousePressEvent(self, event: QMouseEvent):
        if window_behavior.handle_mouse_press(self, event):
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        window_behavior.handle_mouse_move(self, event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        window_behavior.handle_mouse_release(self, event)
        super().mouseReleaseEvent(event)

    def eventFilter(self, obj, event):
        if window_behavior.handle_event_filter(self, obj, event):
            return True
        return super().eventFilter(obj, event)

    def _detect_resize_edges(self, pos: QPoint):
        return window_behavior.detect_resize_edges(self, pos)

    def _cursor_for_edges(self, edges):
        return window_behavior.cursor_for_edges(edges)

    def _update_hover_cursor(self, pos: QPoint):
        window_behavior.update_hover_cursor(self, pos)

    def _resize_from_edge(self, global_pos: QPoint):
        window_behavior.resize_from_edge(self, global_pos)

    def moveEvent(self, event):
        super().moveEvent(event)
        window_behavior.handle_move_event(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        window_behavior.handle_resize_event(self)

    def _create_widgets(self):
        create_window_widgets(self)

    def create_gemini_tab(self):
        build_gemini_tab(self)

    def create_gemini_tab_v2(self):
        build_gemini_tab_v2(self)

    def create_main_tab(self):
        build_main_tab(self)

    def create_audio_tab(self):
        build_audio_tab(self)

    def create_ui_tab(self):
        build_ui_tab(self)

    def create_history_tab(self):
        build_history_tab(self)

    def create_logs_tab(self):
        build_logs_tab(self)

    def create_system_tab(self):
        build_system_tab(self)

    def create_everything_tab(self):
        build_everything_tab(self)

    def on_everything_dir_changed(self):
        return everything_handlers.on_everything_dir_changed(self)

    def on_everything_browse(self):
        return everything_handlers.on_everything_browse(self)

    def on_everything_clear(self):
        return everything_handlers.on_everything_clear(self)

    def on_everything_check(self):
        return everything_handlers.on_everything_check(self)

    def _refresh_everything_status(self, startup_check: bool = False):
        return everything_handlers.refresh_everything_status(self, startup_check)

    def on_request_refresh_everything(self):
        return everything_handlers.on_request_refresh_everything(self)

    def create_vpn_tab(self):
        return build_vpn_tab(self)

    def vless_connect(self):
        return vpn_handlers.vless_connect(self)

    def vless_disconnect(self):
        return vpn_handlers.vless_disconnect(self)

    def vless_test(self):
        return vpn_handlers.vless_test(self)

    def on_vless_enabled_changed(self, state):
        return vpn_handlers.on_vless_enabled_changed(self, state)

    def on_vless_url_changed(self):
        return vpn_handlers.on_vless_url_changed(self)

    def on_vless_autostart_changed(self, state):
        return vpn_handlers.on_vless_autostart_changed(self, state)

    def on_vless_port_changed(self, value):
        return vpn_handlers.on_vless_port_changed(self, value)

    def update_vpn_status(self):
        return vpn_handlers.update_vpn_status(self)

    def _create_layout(self):
        create_window_layout(self)

    def _connect_signals(self):
        connect_window_signals(self)

    def toggle_api_key_visibility(self, state):
        return gemini_handlers.toggle_api_key_visibility(self, state)

    def on_gemini_api_key_changed(self):
        return gemini_handlers.on_gemini_api_key_changed(self)

    def on_gemini_splitter_moved(self, pos, index):
        return gemini_handlers.on_gemini_splitter_moved(self, pos, index)

    def on_gemini_prompt_changed(self):
        return gemini_handlers.on_gemini_prompt_changed(self)

    def on_gemini_prompt_text_changed_profile(self):
        return gemini_handlers.on_gemini_prompt_text_changed_profile(self)

    def on_gemini_markdown_changed(self, state):
        return gemini_handlers.on_gemini_markdown_changed(self, state)

    def on_gemini_prompt_profile_changed(self, name: str):
        return gemini_handlers.on_gemini_prompt_profile_changed(self, name)

    def on_add_gemini_prompt_profile(self):
        return gemini_handlers.on_add_gemini_prompt_profile(self)

    def on_rename_gemini_prompt_profile(self):
        return gemini_handlers.on_rename_gemini_prompt_profile(self)

    def on_delete_gemini_prompt_profile(self):
        return gemini_handlers.on_delete_gemini_prompt_profile(self)

    def on_selection_word_changed(self):
        return settings_handlers.on_selection_word_changed(self)

    def on_pro_word_changed(self):
        return settings_handlers.on_pro_word_changed(self)

    def on_flash_word_changed(self):
        return settings_handlers.on_flash_word_changed(self)

    def on_model_changed(self):
        return settings_handlers.on_model_changed(self)

    def on_autostart_changed(self, state):
        return settings_handlers.on_autostart_changed(self, state)

    def on_start_minimized_changed(self, state):
        return settings_handlers.on_start_minimized_changed(self, state)

    def _set_g3_pro_level(self, level):
        return gemini_handlers._set_g3_pro_level(self, level)

    def on_g3_pro_high_changed(self, state):
        return gemini_handlers.on_g3_pro_high_changed(self, state)

    def on_g3_pro_low_changed(self, state):
        return gemini_handlers.on_g3_pro_low_changed(self, state)

    def on_g3_flash_level_changed(self, button):
        return gemini_handlers.on_g3_flash_level_changed(self, button)

    def on_proxy_changed(self, state):
        return gemini_handlers.on_proxy_changed(self, state)

    def on_proxy_addr_changed(self):
        return gemini_handlers.on_proxy_addr_changed(self)

    def on_proxy_port_changed(self):
        return gemini_handlers.on_proxy_port_changed(self)

    def on_win_shift_mode_changed(self):
        return settings_handlers.on_win_shift_mode_changed(self)

    def on_hold_hotkey_changed(self, value):
        return settings_handlers.on_hold_hotkey_changed(self, value)

    def on_f1_mode_changed(self):
        return settings_handlers.on_f1_mode_changed(self)

    def on_mic_changed(self, index):
        return settings_handlers.on_mic_changed(self, index)

    def on_sound_scheme_changed(self, scheme):
        return settings_handlers.on_sound_scheme_changed(self, scheme)

    def on_quality_check_changed(self, state):
        return settings_handlers.on_quality_check_changed(self, state)

    def on_min_level_changed(self, value):
        return settings_handlers.on_min_level_changed(self, value)

    def on_silence_duration_changed(self, value):
        return settings_handlers.on_silence_duration_changed(self, value)

    def on_vad_changed(self, state):
        return settings_handlers.on_vad_changed(self, state)

    def on_no_speech_changed(self, value):
        return settings_handlers.on_no_speech_changed(self, value)

    def on_logprob_changed(self, value):
        return settings_handlers.on_logprob_changed(self, value)

    def on_condition_prev_changed(self, state):
        return settings_handlers.on_condition_prev_changed(self, state)

    def on_size_setting_changed(self, key, value):
        return settings_handlers.on_size_setting_changed(self, key, value)

    def apply_font_settings(self):
        return settings_handlers.apply_font_settings(self)

    def _update_label_fonts(self):
        return settings_handlers.update_label_fonts(self)

    def _layout_margins_width(self, layout):
        return window_behavior.layout_margins_width(layout)

    def _layout_margins_height(self, layout):
        return window_behavior.layout_margins_height(layout)

    def _available_screen_width(self):
        return window_behavior.available_screen_width(self)

    def _available_screen_height(self):
        return window_behavior.available_screen_height(self)

    def _calculate_compact_min_width(self):
        return window_behavior.calculate_compact_min_width(self)

    def _calculate_expanded_min_width(self):
        return window_behavior.calculate_expanded_min_width(self)

    def _calculate_base_min_height(self):
        return window_behavior.calculate_base_min_height(self)

    def _calculate_compact_min_height(self):
        return window_behavior.calculate_compact_min_height(self)

    def _calculate_tabs_max_height(self):
        return window_behavior.calculate_tabs_max_height(self)

    def _calculate_expanded_min_height(self):
        return window_behavior.calculate_expanded_min_height(self)

    def _sync_size_setting(self, key, value, spin_attr):
        window_behavior.sync_size_setting(self, key, value, spin_attr)

    def _apply_width_floor(self, requested_width, mode):
        return window_behavior.apply_width_floor(self, requested_width, mode)

    def _apply_height_floor(self, requested_height, mode):
        return window_behavior.apply_height_floor(self, requested_height, mode)

    def apply_ui_settings(self):
        return settings_handlers.apply_ui_settings(self)

    def _install_autofit_watchers(self):
        window_behavior.install_autofit_watchers(self)

    def _schedule_expanded_autofit(self):
        window_behavior.schedule_expanded_autofit(self)

    def _apply_expanded_autofit(self):
        window_behavior.apply_expanded_autofit(self)

    def maybe_show_first_run_wizard(self):
        if self.assistant.settings.get("first_run_completed", False):
            return
        self.showNormal()
        self.raise_()
        self.activateWindow()
        wizard = FirstRunWizard(
            self.assistant, self, exe_dir=EXE_DIR, log_func=log_message
        )
        wizard.exec()

    def open_first_run_wizard(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()
        wizard = FirstRunWizard(
            self.assistant, self, exe_dir=EXE_DIR, log_func=log_message
        )
        wizard.exec()

    def _apply_styles(self):
        pass

    def _create_tray_icon(self):
        build_tray_icon(self)

    def _check_tray_visibility(self):
        build_tray_visibility(self)

    def create_colored_icon(self, color):
        return build_tray_colored_icon(color)

    def toggle_pause(self):
        build_tray_pause(self)

    def on_tray_activated(self, reason):
        build_tray_activation(self, reason)

    def show_window(self):
        """Показываем окно БЕЗ изменения позиции если она уже сохранена"""
        self.showNormal()
        self.activateWindow()

        # Позиционируем только если позиция не сохранена
        if (
            self.assistant.settings.get("window_pos_x") is None
            or self.assistant.settings.get("window_pos_y") is None
        ):
            self.position_window()

    def quit_application(self):
        # Завершаем VLESS VPN
        if hasattr(self.assistant, "vless_manager"):
            self.assistant.vless_manager.cleanup()
        # Закрываем экземпляр Everything ассистента
        try:
            if hasattr(self.assistant, "search_handler"):
                self.assistant.search_handler.shutdown_assistant_instance()
        except Exception as e:
            log_message(f"Ошибка остановки Everything на выходе: {e}")
        # Очищаем лог-файл перед выходом, чтобы не накапливался
        try:
            self.assistant.clear_log_file(silent=True)
        except Exception as e:
            log_message(f"Ошибка очистки лога на выходе: {e}")
        self.tray_icon.hide()
        self.assistant.is_running = False
        QApplication.instance().quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        log_message("Окно скрыто в трей")

    def position_window(self):
        """Позиционирование окна с учетом сохраненной позиции"""
        if not self.screen():
            return

        screen_geo = self.screen().availableGeometry()

        # Пытаемся загрузить сохраненную позицию
        saved_x = self.assistant.settings.get("window_pos_x")
        saved_y = self.assistant.settings.get("window_pos_y")

        if saved_x is not None and saved_y is not None:
            # Проверяем что сохраненная позиция в пределах экрана
            if (
                screen_geo.left() <= saved_x <= screen_geo.right() - self.width()
                and screen_geo.top() <= saved_y <= screen_geo.bottom() - self.height()
            ):
                log_message(f"Восстановление позиции окна: ({saved_x}, {saved_y})")
                self.move(saved_x, saved_y)
                return

        # Если нет сохраненной позиции - центрируем
        top_margin = screen_geo.top() + int(screen_geo.height() * 0.1)
        new_x = screen_geo.left() + (screen_geo.width() - self.width()) // 2
        new_y = top_margin

        log_message(f"Новая позиция окна (по умолчанию): ({new_x}, {new_y})")
        self.move(new_x, new_y)

    def update_status(self, text, color, is_processing):
        self.status_label.setText(text)
        self.work_indicator.setVisible(is_processing)

    def update_volume(self, level):
        self.volume_indicator.setValue(level)

    def on_recording_state_changed(self, is_recording):
        self.work_indicator.setVisible(is_recording)
        if hasattr(self, "tray_icon"):
            self.tray_icon.setIcon(
                self.record_icon if is_recording else self.default_icon
            )

    def toggle_settings_panel(self):
        window_behavior.toggle_settings_panel(self)

    def update_history_combo(self):
        return history_handlers.update_history_combo(self)

    def open_log_viewer(self):
        return history_handlers.open_log_viewer(self)

    def clear_logs(self):
        return history_handlers.clear_logs(self)

    def show_selected_history(self):
        return history_handlers.show_selected_history(self)

    def clear_history(self):
        return history_handlers.clear_history(self)

    def open_history_file(self):
        return history_handlers.open_history_file(self)

    def refresh_microphone_list(self):
        return settings_handlers.refresh_microphone_list(self)

