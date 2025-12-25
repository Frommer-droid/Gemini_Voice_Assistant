# -*- coding: utf-8 -*-
"""UI-обработчики для профилей промптов Gemini."""

from PySide6.QtWidgets import QComboBox, QInputDialog, QMessageBox

from app.core.app_config import COLORS
from app.utils.logging_utils import log_message


def on_gemini_prompt_text_changed_profile(window) -> None:
    """Синхронизирует текст редактора с текущим профилем."""
    prompts = window.assistant.settings.get("gemini_prompts", {})
    if not isinstance(prompts, dict):
        prompts = {}
    if hasattr(window, "gemini_prompt_combo") and isinstance(
        window.gemini_prompt_combo, QComboBox
    ):
        name = window.gemini_prompt_combo.currentText()
        if name:
            text = window.gemini_prompt_edit.toPlainText()
            prompts[name] = text
            window.assistant.save_setting("gemini_prompts", prompts)
            window.assistant.save_setting("gemini_selected_prompt", name)
            # Зеркалим в одиночный промпт, чтобы применение шло сразу.
            window.assistant.save_setting("gemini_prompt", text)
            window._last_prompt_profile_name = name


def on_gemini_prompt_profile_changed(window, name: str) -> None:
    prompts = window.assistant.settings.get("gemini_prompts", {})
    if not isinstance(prompts, dict):
        prompts = {}
    previous_name = getattr(window, "_last_prompt_profile_name", None)
    if previous_name and previous_name in prompts:
        prompts[previous_name] = window.gemini_prompt_edit.toPlainText()
        window.assistant.save_setting("gemini_prompts", prompts)
    if name and name in prompts:
        try:
            window.gemini_prompt_edit.blockSignals(True)
            window.gemini_prompt_edit.setPlainText(prompts[name])
        finally:
            window.gemini_prompt_edit.blockSignals(False)
        window.assistant.save_setting("gemini_selected_prompt", name)
        # Зеркалим в одиночный промпт для рантайма
        window.assistant.save_setting("gemini_prompt", prompts[name])
        window.assistant.show_status(
            f"Выбран профиль: {name}", COLORS["accent"], False
        )
        log_message(f"Профиль промпта выбран: {name}")
        window._last_prompt_profile_name = name


def on_add_gemini_prompt_profile(window) -> None:
    text, ok = QInputDialog.getText(
        window, "Новый профиль", "Введите название профиля:"
    )
    name = text.strip()
    if not ok or not name:
        return
    prompts = window.assistant.settings.get("gemini_prompts", {})
    if name in prompts:
        QMessageBox.warning(
            window, "Ошибка", "Профиль с таким именем уже существует."
        )
        return
    prompts[name] = ""
    window.assistant.save_setting("gemini_prompts", prompts)
    window.gemini_prompt_combo.addItem(name)
    window.gemini_prompt_combo.setCurrentText(name)
    try:
        window.gemini_prompt_edit.blockSignals(True)
        window.gemini_prompt_edit.setPlainText("")
    finally:
        window.gemini_prompt_edit.blockSignals(False)
    window.assistant.save_setting("gemini_selected_prompt", name)
    window.assistant.save_setting("gemini_prompt", "")
    window.assistant.show_status("Профиль добавлен", COLORS["accent"], False)


def on_rename_gemini_prompt_profile(window) -> None:
    current = window.gemini_prompt_combo.currentText()
    if not current:
        return
    text, ok = QInputDialog.getText(
        window, "Переименовать профиль", "Новое имя:", text=current
    )
    new_name = text.strip()
    if not ok or not new_name or new_name == current:
        return
    prompts = window.assistant.settings.get("gemini_prompts", {})
    if new_name in prompts:
        QMessageBox.warning(
            window, "Ошибка", "Профиль с таким именем уже существует."
        )
        return
    prompts[new_name] = prompts.pop(
        current, window.gemini_prompt_edit.toPlainText()
    )
    window.assistant.save_setting("gemini_prompts", prompts)
    window.assistant.save_setting("gemini_selected_prompt", new_name)
    window.gemini_prompt_combo.blockSignals(True)
    window.gemini_prompt_combo.clear()
    for n in prompts.keys():
        window.gemini_prompt_combo.addItem(n)
    window.gemini_prompt_combo.setCurrentText(new_name)
    window.gemini_prompt_combo.blockSignals(False)
    window.assistant.show_status(
        "Профиль переименован", COLORS["accent"], False
    )


def on_delete_gemini_prompt_profile(window) -> None:
    prompts = window.assistant.settings.get("gemini_prompts", {})
    if len(prompts) <= 1:
        QMessageBox.information(
            window, "Информация", "Нельзя удалить единственный профиль."
        )
        return
    current = window.gemini_prompt_combo.currentText()
    reply = QMessageBox.question(
        window,
        "Удаление профиля",
        f"Удалить профиль '{current}'?",
        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        QMessageBox.StandardButton.No,
    )
    if reply != QMessageBox.StandardButton.Yes:
        return
    if current in prompts:
        prompts.pop(current)
        window.assistant.save_setting("gemini_prompts", prompts)
    window.gemini_prompt_combo.blockSignals(True)
    window.gemini_prompt_combo.clear()
    for n in prompts.keys():
        window.gemini_prompt_combo.addItem(n)
    first = next(iter(prompts.keys())) if prompts else ""
    window.gemini_prompt_combo.setCurrentText(first)
    window.gemini_prompt_combo.blockSignals(False)
    new_text = prompts.get(first, "")
    try:
        window.gemini_prompt_edit.blockSignals(True)
        window.gemini_prompt_edit.setPlainText(new_text)
    finally:
        window.gemini_prompt_edit.blockSignals(False)
    window.assistant.save_setting("gemini_selected_prompt", first)
    window.assistant.save_setting("gemini_prompt", new_text)
    window.assistant.show_status("Профиль удален", COLORS["accent"], False)
