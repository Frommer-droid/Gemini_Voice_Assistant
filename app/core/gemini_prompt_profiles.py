# -*- coding: utf-8 -*-
"""Работа с профилями промптов Gemini на уровне настроек."""

import json

from app.core.app_config import SETTINGS_FILE
from app.utils.logging_utils import log_message


def apply_prompt_profile(assistant, profile_name):
    prompts = assistant.settings.get("gemini_prompts", {})
    if not isinstance(prompts, dict):
        log_message(
            "Невозможно применить профиль: список промптов отсутствует или повреждён"
        )
        return None

    prompt_text = prompts.get(profile_name)
    if prompt_text is None:
        log_message(f"Профиль промпта '{profile_name}' не найден")
        return None

    assistant.settings["gemini_selected_prompt"] = profile_name
    assistant.settings["gemini_prompt"] = prompt_text

    try:
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(assistant.settings, f, indent=2, ensure_ascii=False)
        log_message(f"Активирован профиль промпта: {profile_name}")
    except Exception as e:
        log_message(f"Не удалось сохранить профиль '{profile_name}': {e}")

    return prompt_text
