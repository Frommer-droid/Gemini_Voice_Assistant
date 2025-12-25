# -*- coding: utf-8 -*-
"""Обработка команд, хоткеев и маршрутизации."""

import time
import traceback
from typing import Optional

from pynput import keyboard

from app.core import gemini_processing
from app.core import gemini_prompt_profiles as gemini_prompt_profiles_core
from app.core.app_config import COLORS, CONTINUOUS_HOTKEY
from app.core.settings_store import normalize_hold_hotkey
from app.utils.logging_utils import log_message


class VoiceAssistantCommandMixin:
    def _build_hotkey_combo(self, name: str):
        """Возвращает набор клавиш для удержания записи."""
        mapping = {
            "win+shift": {keyboard.Key.cmd, keyboard.Key.shift},
            "ctrl+shift": {keyboard.Key.ctrl, keyboard.Key.shift},
        }
        return mapping.get((name or "").lower(), mapping["win+shift"])

    def update_hotkey_combo(self, name: Optional[str] = None):
        """Обновляет сочетание удержания записи."""
        name = normalize_hold_hotkey(
            name or self.settings.get("hold_hotkey") or "win+shift"
        )
        self.settings["hold_hotkey"] = name
        self.hotkey_combo = self._build_hotkey_combo(name)
        self.normalized_hotkey_combo = {
            self.key_to_comparable(k) for k in self.hotkey_combo
        }

    def _update_cached_settings(self):
        """Кэширует часто используемые настройки."""
        self.win_shift_mode = self.settings.get("win_shift_mode", "Обычный")
        self.f1_mode = self.settings.get("f1_mode", "Непрерывный")
        self.hold_hotkey = normalize_hold_hotkey(
            self.settings.get("hold_hotkey", "win+shift")
        )
        self.settings["hold_hotkey"] = self.hold_hotkey
        self.hotkey_combo = self._build_hotkey_combo(self.hold_hotkey)
        self.normalized_hotkey_combo = {
            self.key_to_comparable(k) for k in self.hotkey_combo
        }
        log_message(
            "Кэшированные настройки обновлены: "
            f"win_shift='{self.win_shift_mode}', f1='{self.f1_mode}', "
            f"hold_hotkey='{self.hold_hotkey}', combo={self.normalized_hotkey_combo}"
        )

    def run(self):
        try:
            with keyboard.Listener(
                on_press=self.on_press, on_release=self.on_release
            ) as listener:
                log_message(
                    f"Горячие клавиши запущены (удержание: {self.hold_hotkey})."
                )
                while self.is_running:
                    time.sleep(0.1)
                listener.stop()
        except Exception as e:
            log_message(f"Критическая ошибка горячих клавиш: {e}")
            log_message(traceback.format_exc())

    def key_to_comparable(self, key):
        """
        Нормализует клавишу для сравнения хоткеев:
        - левый/правый Ctrl -> Key.ctrl
        - левый/правый Alt/AltGr -> Key.alt
        - левый/правый Shift -> Key.shift
        - левый/правый Cmd -> Key.cmd
        - буквенно-цифровые -> строчные символы
        """
        try:
            from pynput.keyboard import Key

            if key in (Key.ctrl_l, Key.ctrl_r, Key.ctrl):
                return Key.ctrl
            if key in (Key.alt_l, Key.alt_r, Key.alt_gr, Key.alt):
                return Key.alt
            if key in (Key.shift_l, Key.shift_r, Key.shift):
                return Key.shift
            if key in (Key.cmd_l, Key.cmd_r, Key.cmd):
                return Key.cmd
            if hasattr(key, "char") and key.char:
                char = key.char
                # Игнорируем управляющие символы (ctrl передается как \x11 и т.п.)
                if len(char) == 1 and ord(char) >= 32:
                    return char.lower()
                return key
            return key
        except Exception:
            return key

    def _update_hold_recording_state(self):
        if not self.normalized_hotkey_combo:
            return

        active_hotkey = self.normalized_hotkey_combo.issubset(self.pressed_keys)
        if active_hotkey:
            if not self.is_recording and not self.is_continuous_recording:
                log_message(
                    "Горячая клавиша удержания сработала: "
                    f"{self.normalized_hotkey_combo}"
                )
                self.start_recording(
                    continuous=self.win_shift_mode == "Непрерывный",
                    source="hold",
                )
            return

        if self._recording_hotkey_source == "hold" and (
            self.is_recording or self.is_continuous_recording
        ):
            self.stop_recording(continuous=self.is_continuous_recording)

    def on_press(self, key):
        if self.is_paused:
            return

        if key == CONTINUOUS_HOTKEY:
            is_continuous = self.f1_mode == "Непрерывный"
            if self.is_recording or self.is_continuous_recording:
                self.stop_recording(continuous=is_continuous)
            else:
                self.start_recording(continuous=is_continuous, source="f1")
            return

        with self.keys_lock:
            comparable_key = self.key_to_comparable(key)
            before_size = len(self.pressed_keys)
            self.pressed_keys.add(comparable_key)
            if (
                comparable_key in self.normalized_hotkey_combo
                and len(self.pressed_keys) != before_size
            ):
                log_message(
                    "Нажата клавиша хоткея: "
                    f"{comparable_key}, текущее множество: {self.pressed_keys}"
                )
            self._update_hold_recording_state()

    def on_release(self, key):
        if self.is_paused:
            return

        with self.keys_lock:
            comparable_key = self.key_to_comparable(key)
            if comparable_key in self.pressed_keys:
                self.pressed_keys.discard(comparable_key)
                if comparable_key in self.normalized_hotkey_combo:
                    log_message(
                        "Отпущена клавиша хоткея: "
                        f"{comparable_key}, текущее множество: {self.pressed_keys}"
                    )
            self._update_hold_recording_state()

    def _apply_prompt_profile(self, profile_name):
        return gemini_prompt_profiles_core.apply_prompt_profile(self, profile_name)

    def _next_cancel_seq(self):
        with self._cancel_lock:
            self._cancel_seq += 1
            return self._cancel_seq

    def _get_cancel_seq(self):
        with self._cancel_lock:
            return self._cancel_seq

    def _is_cancelled(self, seq):
        with self._cancel_lock:
            return self._cancel_seq != seq

    def cancel_all_operations(self, source: str = ""):
        self._next_cancel_seq()
        self._cancel_pending.set()
        if self.is_recording or self.is_continuous_recording:
            self.stop_recording(continuous=self.is_continuous_recording)
        self._gemini_cancel_event.set()
        with self._task_lock:
            self._current_task_id += 1
            self._task_finalized = True
            self._is_gemini_processing = False
            self._current_task_text = ""
            self._current_task_insert_text = False
        if self.audio_buffer:
            self.audio_buffer.clear()
        if self.pressed_keys:
            self.pressed_keys.clear()
        if source:
            log_message(f"Принудительная отмена всех операций: {source}")
        else:
            log_message("Принудительная отмена всех операций.")
        self.show_status("Операции остановлены", COLORS["btn_warning"], False)
        return True

    def cancel_gemini_processing(self):
        return gemini_processing.cancel_gemini_processing(self)

    def _handle_final_text(
        self,
        text,
        insert_text=False,
        use_pro=False,
        use_flash=False,
        use_selection=False,
        active_profile=None,
        prompt_override=None,
        cancel_seq=None,
    ):
        """Обработка финального текста с отправкой в Gemini."""
        return gemini_processing.handle_final_text(
            self,
            text,
            insert_text=insert_text,
            use_pro=use_pro,
            use_flash=use_flash,
            use_selection=use_selection,
            active_profile=active_profile,
            prompt_override=prompt_override,
            cancel_seq=cancel_seq,
        )
