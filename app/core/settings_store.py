# -*- coding: utf-8 -*-
import json
import os
from typing import Optional

from app.core.app_config import DEFAULT_SETTINGS, SETTINGS_FILE
from app.utils.logging_utils import log_message


def normalize_hold_hotkey(name: Optional[str], log_func=log_message) -> str:
    """Приводит сочетание удержания к поддерживаемому виду."""
    allowed = {"win+shift", "ctrl+shift"}
    normalized = (name or "win+shift").lower()
    if normalized not in allowed:
        log_func(
            f"Сочетание удержания '{name}' не поддерживается. Используем Win+Shift."
        )
        normalized = "win+shift"
    return normalized


class SettingsStore:
    def __init__(
        self,
        settings_file: str = SETTINGS_FILE,
        default_settings: Optional[dict] = None,
        log_func=log_message,
    ) -> None:
        self.settings_file = settings_file
        self.default_settings = default_settings or DEFAULT_SETTINGS
        self.log = log_func

    def load_settings(self) -> dict:
        settings = self.default_settings.copy()
        try:
            if os.path.exists(self.settings_file):
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    loaded_settings = json.load(f)
                settings.update(loaded_settings)
                if "first_run_completed" not in loaded_settings:
                    settings["first_run_completed"] = True
                    try:
                        self.save_settings(settings)
                        self.log(
                            "first_run_completed установлен для существующих настроек."
                        )
                    except Exception as e:
                        self.log(f"Ошибка сохранения first_run_completed: {e}")
                self.log(f"Настройки загружены из {self.settings_file}")

                # Cleanup possible mojibake in stored strings
                def _clean_text(val, fallback):
                    if isinstance(val, str) and ("\ufffd" in val or "?" in val):
                        return fallback
                    return val

                settings["selection_word"] = _clean_text(
                    settings.get("selection_word"), "выделить"
                )
                settings["pro_word"] = _clean_text(settings.get("pro_word"), "про")
                settings["flash_word"] = _clean_text(settings.get("flash_word"), "флеш")
                settings["sound_scheme"] = _clean_text(
                    settings.get("sound_scheme"), "Стандартные"
                )
                settings["win_shift_mode"] = _clean_text(
                    settings.get("win_shift_mode"), "Обычный"
                )
                settings["f1_mode"] = _clean_text(
                    settings.get("f1_mode"), "Непрерывный"
                )
                settings["hold_hotkey"] = _clean_text(
                    settings.get("hold_hotkey"), "win+shift"
                )
                settings["everything_dir"] = _clean_text(
                    settings.get("everything_dir"), ""
                )
                if "silence_detection_enabled" not in settings:
                    settings["silence_detection_enabled"] = settings.get(
                        "audio_quality_check", True
                    )
                self._apply_settings_migrations(settings)
        except Exception as e:
            self.log(f"Ошибка загрузки настроек: {e}")
        return settings

    def save_settings(self, settings: dict) -> None:
        with open(self.settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)

    def _apply_settings_migrations(self, settings: dict) -> None:
        """Мигрирует ключевые настройки на Gemini 3."""
        migrations = {
            "gemini_model_pro": {
                "gemini-2.5-pro": "gemini-3-pro-preview",
                "gemini-1.5-pro": "gemini-3-pro-preview",
            },
            "gemini_model_default": {
                "gemini-3-pro-preview": "gemini-2.5-flash",  # Legacy fallback if user had this
                "gemini-2.5-flash": "gemini-3-flash-preview",
            },
        }
        updated = False
        extra_updated = False
        for key, replacements in migrations.items():
            current_value = settings.get(key)
            if current_value in replacements:
                new_value = replacements[current_value]
                settings[key] = new_value
                updated = True
                self.log(
                    f"Миграция настройки '{key}' на Gemini 3 ({current_value} -> {new_value})"
                )
        current_hold = settings.get("hold_hotkey")
        normalized_hold = normalize_hold_hotkey(current_hold, self.log)
        if normalized_hold != current_hold:
            settings["hold_hotkey"] = normalized_hold
            updated = True
        if updated:
            try:
                self.save_settings(settings)
                self.log("Настройки сохранены после миграции на Gemini 3.")
            except Exception as e:
                self.log(f"Не удалось сохранить настройки после миграции: {e}")
        # Migrating old thinking level to Pro level
        if "gemini3_thinking_level" in settings:
            if "gemini3_pro_thinking_level" not in settings:
                settings["gemini3_pro_thinking_level"] = settings.pop(
                    "gemini3_thinking_level"
                )
                extra_updated = True
            else:
                # Just remove the old key if new one exists
                settings.pop("gemini3_thinking_level")
                extra_updated = True

        # Initialize Flash level if missing
        if "gemini3_flash_thinking_level" not in settings:
            settings["gemini3_flash_thinking_level"] = "high"
            extra_updated = True

        # Cleanup old 2.5 settings
        if "gemini25_flash_mode" in settings:
            settings.pop("gemini25_flash_mode")
            extra_updated = True

        if extra_updated:
            try:
                self.save_settings(settings)
                self.log(
                    "Доп. миграции настроек thinking (Pro/Flash split) применены."
                )
            except Exception as e:
                self.log(f"Ошибка записи настроек после миграции thinking: {e}")
