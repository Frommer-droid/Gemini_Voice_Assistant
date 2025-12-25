# -*- coding: utf-8 -*-
"""Основная бизнес-логика приложения."""

import os
import threading
from typing import Optional

from app.commands.command_router import CommandRouter
from app.core.app_config import (
    COLORS,
    EXE_DIR,
    LANGUAGE,
    WHISPER_MODELS_DIR,
    format_path_for_log,
)
from app.core.gemini_client import GeminiClientManager
from app.core.settings_store import SettingsStore
from app.core.voice_assistant_audio import VoiceAssistantAudioMixin
from app.core.voice_assistant_commands import VoiceAssistantCommandMixin
from app.core.voice_assistant_output import VoiceAssistantOutputMixin
from app.services.everything_search import EverythingSearchHandler
from app.services.vless_manager import VLESSManager
from app.speech.whisper_engine import WhisperEngine
from app.utils.logging_utils import log_message


class VoiceAssistant(
    VoiceAssistantAudioMixin, VoiceAssistantCommandMixin, VoiceAssistantOutputMixin
):
    def __init__(self):
        self.is_recording = False
        self.is_continuous_recording = False
        self.is_running = True
        self.is_paused = False
        self.keys_lock = threading.Lock()
        self.pressed_keys = set()
        self.normalized_hotkey_combo = set()
        self.ui_signals = None
        self.start_time = 0
        self._gemini_cancel_event = threading.Event()
        self._task_lock = threading.Lock()
        self._current_task_id = 0
        self._task_finalized = False
        self._current_task_text = ""
        self._current_task_insert_text = False
        self._is_gemini_processing = False
        self._recording_hotkey_source = None
        self._cancel_lock = threading.Lock()
        self._cancel_seq = 0
        self._cancel_pending = threading.Event()
        self.settings_store = SettingsStore()
        self.settings = self.settings_store.load_settings()
        self.gemini_manager = GeminiClientManager(log_func=log_message)
        if self.gemini_manager.supports_thinking_level:
            log_message(
                "Обнаружена поддержка Gemini thinking_level, используем новый режим."
            )
        else:
            log_message(
                "thinking_level недоступен в установленной библиотеке, fallback на thinking_budget."
            )
        # Инициализация VLESS VPN менеджера с настраиваемым портом
        vless_port = int(self.settings.get("vless_port", 10809))
        self.vless_manager = VLESSManager(log_func=log_message, socks_port=vless_port)
        log_message(f"VLESS VPN инициализирован на порту: {vless_port}")
        # Модуль поиска через Everything
        self.search_handler = EverythingSearchHandler(log_message)
        self.search_handler.instance_name = (
            self.settings.get("everything_instance_name") or None
        )
        self.search_handler.previous_instance_name = (
            self.settings.get("everything_previous_instance") or None
        )
        self.update_everything_paths(self.settings.get("everything_dir", ""))
        self.command_router = CommandRouter(self, log_func=log_message)
        self._everything_warmup_complete = False
        self._everything_warmup_in_progress = False
        self._everything_warmup_pending = False
        self._everything_warmup_pending_force = False
        if self.settings.get("first_run_completed", False):
            self.warmup_everything_async()
        else:
            log_message(
                "Первый запуск: автозапуск Everything отложен до завершения мастера."
            )

        # Автозапуск VLESS если включено
        if self.settings.get("vless_enabled", False) and self.settings.get(
            "vless_autostart", False
        ):
            vless_url = self.settings.get("vless_url", "")
            if vless_url:
                log_message("🔄 Автозапуск VLESS VPN...")
                if self.vless_manager.start(vless_url):
                    log_message("✅ VPN автоматически подключен при запуске")
                else:
                    log_message("⚠️ Не удалось автоматически подключить VPN")
                    log_message(
                        "   Проверьте правильность VLESS URL и доступность сервера"
                    )
            else:
                log_message("⚠️ Автозапуск VPN включен, но URL не указан")

        self._update_cached_settings()
        self.setup_audio()
        self.client = None
        self.setup_gemini()

        # ИСПРАВЛЕНО: НЕ загружаем модель автоматически
        self.whisper_engine = WhisperEngine(
            WHISPER_MODELS_DIR, LANGUAGE, log_func=log_message
        )
        self.clipboard_at_start = ""
        self.selection_text = ""

        self.audio_buffer = []

    def post_ui_init(self):
        """Выполняется после инициализации UI для авто-активации модели."""
        selected_model = self.settings.get("whisper_model")
        log_message(
            f"Проверка авто-активации для модели '{selected_model}' при запуске..."
        )
        if self.is_model_downloaded(selected_model):
            log_message(
                f"Модель '{selected_model}' найдена локально. Запуск фоновой активации..."
            )
            threading.Thread(
                target=self.setup_whisper, args=(selected_model,), daemon=True
            ).start()
        else:
            log_message(
                f"Модель '{selected_model}' не найдена локально. Требуется ручная загрузка."
            )
            self.show_status(
                f"Модель {selected_model} не скачана", COLORS["btn_warning"], False
            )

        if self._everything_warmup_complete:
            self._emit_everything_status_refresh()

    def _warmup_everything(self, force_start: bool = False):
        try:
            if not os.path.exists(self.search_handler.es_path):
                log_message("es.exe не найден, автозапуск Everything пропущен.")
                return
            if self.search_handler.ensure_everything_running(
                timeout_s=10.0, force_start=force_start
            ):
                log_message("Everything готов к поиску.")
            else:
                log_message("Everything недоступен. Поиск может не работать.")
        finally:
            self._everything_warmup_complete = True
            self._emit_everything_status_refresh()

    def _emit_everything_status_refresh(self):
        if self.ui_signals:
            self.ui_signals.request_refresh_everything.emit()

    def warmup_everything_async(self, force_start: bool = False):
        if self._everything_warmup_in_progress:
            self._everything_warmup_pending = True
            if force_start:
                self._everything_warmup_pending_force = True
            return

        self._everything_warmup_in_progress = True

        def _task():
            try:
                self._warmup_everything(force_start=force_start)
            finally:
                self._everything_warmup_in_progress = False
                if self._everything_warmup_pending:
                    pending_force = self._everything_warmup_pending_force
                    self._everything_warmup_pending = False
                    self._everything_warmup_pending_force = False
                    self.warmup_everything_async(force_start=pending_force)

        threading.Thread(target=_task, daemon=True).start()

    def save_setting(self, key, value):
        if key == "everything_dir":
            value = ""
        self.settings[key] = value
        if key == "everything_dir":
            self.update_everything_paths(None)
        try:
            self.settings_store.save_settings(self.settings)

            # Обновляем кэш, если изменилась настройка хоткея
            if key in ["win_shift_mode", "f1_mode", "hold_hotkey"]:
                self._update_cached_settings()

        except Exception as e:
            log_message(f"Ошибка сохранения настройки '{key}': {e}")

    def update_everything_paths(self, base_dir: Optional[str] = None):
        internal_dir = os.path.normpath(
            os.path.join(EXE_DIR, "_internal", "Everything")
        )
        self.search_handler.update_paths(EXE_DIR)
        if self.search_handler.instance_name:
            self.search_handler.previous_instance_name = (
                self.search_handler.instance_name
            )
        self.search_handler.instance_name = self.search_handler.default_instance_name
        self.settings["everything_instance_name"] = (
            self.search_handler.instance_name or ""
        )
        self.settings["everything_previous_instance"] = (
            self.search_handler.previous_instance_name or ""
        )
        log_message(f"Экземпляр Everything: {self.search_handler.instance_name}")
        active_dir = ""
        if self.search_handler.everything_path:
            active_dir = os.path.dirname(self.search_handler.everything_path)
        elif self.search_handler.es_path:
            active_dir = os.path.dirname(self.search_handler.es_path)

        if active_dir:
            path_label = format_path_for_log(active_dir) or active_dir
            log_message(f"Папка Everything (активная): {path_label}")
        else:
            path_label = format_path_for_log(internal_dir) or internal_dir
            log_message(f"Папка Everything (ожидается): {path_label}")
        es_label = format_path_for_log(self.search_handler.es_path) or self.search_handler.es_path
        log_message(f"es.exe для поиска: {es_label}")
        if self.search_handler.everything_path:
            exe_label = (
                format_path_for_log(self.search_handler.everything_path)
                or self.search_handler.everything_path
            )
            log_message(f"Everything.exe для запуска: {exe_label}")
        else:
            log_message("Everything.exe для автозапуска не найден.")

    def setup_gemini(self):
        self.client = self.gemini_manager.initialize(self.settings, self.vless_manager)

    def reinitialize_gemini(self):
        """Переинициализация клиента Gemini для применения новых настроек"""
        log_message("Переинициализация клиента Gemini...")
        self.show_status("Применение настроек Gemini...", COLORS["accent"], True)
        self.setup_gemini()
        self.show_status("Настройки Gemini применены", COLORS["accent"], False)


