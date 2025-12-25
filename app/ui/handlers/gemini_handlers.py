# -*- coding: utf-8 -*-
"""Обработчики Gemini-настроек и профилей промптов."""

from PySide6.QtWidgets import QLineEdit

from app.core.app_config import COLORS
from app.ui import gemini_prompt_profiles as gemini_prompt_profiles_ui
from app.utils.logging_utils import log_message


def toggle_api_key_visibility(window, state) -> None:
    """Показать/скрыть API ключ"""
    if state:
        window.gemini_api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
    else:
        window.gemini_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)


def on_gemini_api_key_changed(window) -> None:
    """Обработчик изменения API ключа"""
    api_key = window.gemini_api_key_edit.text().strip()
    window.assistant.save_setting("gemini_api_key", api_key)

    if api_key:
        window.assistant.show_status(
            "API ключ Gemini сохранён", COLORS["accent"], False
        )
        window.assistant.setup_gemini()
    else:
        window.assistant.show_status(
            "API ключ Gemini очищен", COLORS["btn_warning"], False
        )

    log_message("API ключ Gemini обновлён")


def on_gemini_splitter_moved(window, pos, index) -> None:
    height = window.gemini_splitter.sizes()[1]
    window.assistant.save_setting("gemini_prompt_height", height)


def on_gemini_prompt_changed(window) -> None:
    window.assistant.save_setting(
        "gemini_prompt", window.gemini_prompt_edit.toPlainText()
    )
    window.assistant.show_status("Промпт Gemini сохранен", COLORS["accent"], False)


def on_gemini_prompt_text_changed_profile(window) -> None:
    gemini_prompt_profiles_ui.on_gemini_prompt_text_changed_profile(window)


def on_gemini_markdown_changed(window, state) -> None:
    enabled = bool(state)
    window.assistant.save_setting("gemini_markdown_enabled", enabled)
    status = "разрешен" if enabled else "запрещен"
    window.assistant.show_status(f"Markdown {status}", COLORS["accent"], False)
    log_message(f"Markdown {status}")


def on_gemini_prompt_profile_changed(window, name: str) -> None:
    gemini_prompt_profiles_ui.on_gemini_prompt_profile_changed(window, name)


def on_add_gemini_prompt_profile(window) -> None:
    gemini_prompt_profiles_ui.on_add_gemini_prompt_profile(window)


def on_rename_gemini_prompt_profile(window) -> None:
    gemini_prompt_profiles_ui.on_rename_gemini_prompt_profile(window)


def on_delete_gemini_prompt_profile(window) -> None:
    gemini_prompt_profiles_ui.on_delete_gemini_prompt_profile(window)


def _set_g3_pro_level(window, level) -> None:
    level = "high" if level == "high" else "low"
    window.g3_pro_high_check.blockSignals(True)
    window.g3_pro_low_check.blockSignals(True)
    window.g3_pro_high_check.setChecked(level == "high")
    window.g3_pro_low_check.setChecked(level == "low")
    window.g3_pro_high_check.blockSignals(False)
    window.g3_pro_low_check.blockSignals(False)
    window.assistant.save_setting("gemini3_pro_thinking_level", level)
    window.assistant.show_status(f"Gemini 3.0 Pro: {level}", COLORS["accent"], False)


def on_g3_pro_high_changed(window, state) -> None:
    if state:
        _set_g3_pro_level(window, "high")
    elif not window.g3_pro_low_check.isChecked():
        _set_g3_pro_level(window, "high")


def on_g3_pro_low_changed(window, state) -> None:
    if state:
        _set_g3_pro_level(window, "low")
    elif not window.g3_pro_high_check.isChecked():
        _set_g3_pro_level(window, "low")


def on_g3_flash_level_changed(window, button) -> None:
    text = button.text().lower()
    window.assistant.save_setting("gemini3_flash_thinking_level", text)
    window.assistant.show_status(
        f"Gemini 3.0 Flash: {text}", COLORS["accent"], False
    )


def on_proxy_changed(window, state) -> None:
    enabled = bool(state)
    window.assistant.save_setting("proxy_enabled", enabled)
    status = "включен" if enabled else "выключен"
    window.assistant.show_status(f"Прокси {status}", COLORS["accent"], False)
    window.assistant.reinitialize_gemini()


def on_proxy_addr_changed(window) -> None:
    window.assistant.save_setting("proxy_address", window.proxy_addr_edit.text())
    window.assistant.show_status("Адрес прокси сохранен", COLORS["accent"], False)
    if window.assistant.settings.get("proxy_enabled"):
        window.assistant.reinitialize_gemini()


def on_proxy_port_changed(window) -> None:
    window.assistant.save_setting("proxy_port", window.proxy_port_edit.text())
    window.assistant.show_status("Порт прокси сохранен", COLORS["accent"], False)
    if window.assistant.settings.get("proxy_enabled"):
        window.assistant.reinitialize_gemini()
