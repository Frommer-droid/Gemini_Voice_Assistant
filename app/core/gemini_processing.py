# -*- coding: utf-8 -*-
"""Gemini-обработка: подготовка промпта, запрос и завершение задачи."""

import datetime
import os
import re
import subprocess
import threading
import time
import traceback

import pyperclip

from app.core.app_config import COLORS, resource_path
from app.core.gemini_client import GeminiCancelledError
from app.utils.logging_utils import history_logger, log_message, log_separator


def begin_gemini_task(assistant, whisper_text, insert_text):
    text = (whisper_text or "").strip()
    with assistant._task_lock:
        assistant._current_task_id += 1
        assistant._task_finalized = False
        assistant._current_task_text = text
        assistant._current_task_insert_text = insert_text
        assistant._is_gemini_processing = True
        assistant._gemini_cancel_event.clear()
        return assistant._current_task_id


def finalize_task_output(
    assistant,
    final_text,
    insert_text,
    task_id,
    status_text=None,
    status_color=None,
    spinning=False,
):
    final_text = (final_text or "").strip()
    with assistant._task_lock:
        if task_id != assistant._current_task_id or assistant._task_finalized:
            return False
        insert = (
            assistant._current_task_insert_text
            if insert_text is None
            else insert_text
        )
        assistant._task_finalized = True
        assistant._is_gemini_processing = False

    if assistant.audio_buffer:
        log_message(
            "Сбрасываем буфер сегментов Whisper "
            f"(элементов: {len(assistant.audio_buffer)})"
        )
        assistant.audio_buffer.clear()

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        history_logger.info(f"{timestamp}\n{final_text}\n---")
        log_message("Запись добавлена в историю")
    except Exception as e:
        log_message(f"Ошибка записи в историю: {e}")

    if assistant.ui_signals:
        assistant.ui_signals.history_updated.emit()

    if insert:
        try:
            pyperclip.copy(final_text)
            log_message("Текст сохранен в буфер обмена")
        except Exception as e:
            log_message(f"Ошибка копирования в буфер: {e}")

        ahk_exe = resource_path("paste_text.exe")
        if os.path.exists(ahk_exe):
            try:
                subprocess.Popen(
                    [ahk_exe, final_text], creationflags=subprocess.CREATE_NO_WINDOW
                )
                log_message("Текст отправлен через AHK")
            except Exception as e:
                log_message(f"Ошибка AHK: {e}")
        else:
            log_message("AHK не найден, текст оставлен в буфере обмена")

        if assistant.ui_signals:
            assistant.ui_signals.request_hide_window.emit()

        message = status_text or f"Готово! ({len(final_text)} симв.)"
        assistant.show_status(message, status_color or COLORS["accent"], False)
        total_time = time.time() - assistant.start_time
        log_message(f"Полный цикл от старта до вставки: {total_time:.2f}с.")
        log_separator()
        threading.Timer(
            2.0,
            lambda: assistant.show_status(
                "Готов к работе", COLORS["accent"], False
            ),
        ).start()
    else:
        if status_text:
            assistant.show_status(
                status_text, status_color or COLORS["accent"], spinning
            )
    return True


def strip_markdown_text(text: str) -> str:
    """Удаляет базовую Markdown-разметку, сохраняя читаемый текст."""
    if not isinstance(text, str):
        return text
    cleaned = text

    def _strip_fence(match):
        block = match.group(0)
        block = re.sub(r"^```[^\n]*\n?", "", block)
        block = re.sub(r"\n?```$", "", block)
        return block.strip("\n")

    cleaned = re.sub(r"```[\s\S]*?```", _strip_fence, cleaned)
    cleaned = re.sub(r"(?m)^```.*$", "", cleaned)
    cleaned = re.sub(r"(?m)^~~~.*$", "", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r"\1 (\2)", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", cleaned)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*(\S[^*]*?)\*", r"\1", cleaned)
    cleaned = re.sub(r"(?m)^#{1,6}\s+", "", cleaned)
    cleaned = re.sub(r"(?m)^>\s+", "", cleaned)
    cleaned = re.sub(r"(?m)^[-*_]{3,}\s*$", "", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _debug_preview(text: str, limit: int = 800) -> str:
    text = "" if text is None else str(text)
    if len(text) <= limit:
        return text
    return f"{text[:limit]}... [обрезано, всего {len(text)} симв.]"


def _is_auxiliary_part(text: str) -> bool:
    stripped = (text or "").strip()
    if not stripped:
        return False
    lowered = stripped.lower()
    markers = (
        "thought",
        "thoughts",
        "thoughtful",
        "thought-process",
        "mini-thought-process",
        "thinking",
        "reasoning",
        "analysis",
    )
    if any(marker in lowered for marker in markers):
        return True
    if "```" in stripped:
        return True
    if "note:" in lowered:
        return True
    return False


def _extract_response_text(response) -> str:
    fallback_text = getattr(response, "text", "") or ""
    candidates = getattr(response, "candidates", None) or []
    if not candidates:
        return fallback_text
    content = getattr(candidates[0], "content", None)
    parts = getattr(content, "parts", None) or []
    if not parts:
        return fallback_text
    text_parts = [getattr(part, "text", None) for part in parts]
    text_parts = [text for text in text_parts if text is not None]
    if not text_parts:
        return fallback_text
    suspicious = []
    clean = []
    for part in parts:
        part_text = getattr(part, "text", None)
        if part_text is None:
            continue
        if getattr(part, "thought", False):
            skipped = part_text.strip()
            if skipped:
                suspicious.append(skipped)
            continue
        if _is_auxiliary_part(part_text):
            suspicious.append(part_text.strip())
        else:
            clean.append(part_text)
    if clean:
        if suspicious:
            preview = "; ".join(_debug_preview(text, 80) for text in suspicious)
            log_message(
                "DEBUG: Пропущены служебные части ответа Gemini: "
                f"{preview}"
            )
        return "\n".join(part.rstrip() for part in clean).strip()
    return fallback_text


def _log_response_structure(response) -> None:
    try:
        candidates = getattr(response, "candidates", None) or []
        log_message(f"DEBUG: Кандидатов Gemini: {len(candidates)}")
        for idx, candidate in enumerate(candidates):
            content = getattr(candidate, "content", None)
            parts = getattr(content, "parts", None) or []
            log_message(f"DEBUG: Кандидат {idx}: частей={len(parts)}")
            for pidx, part in enumerate(parts):
                part_text = getattr(part, "text", None)
                part_thought = getattr(part, "thought", False)
                if part_text is not None:
                    preview = _debug_preview(part_text, 200)
                    log_message(
                        "DEBUG:  part["
                        f"{pidx}] text({len(part_text)}), thought={part_thought}: "
                        f"{preview}"
                    )
                    continue
                if getattr(part, "function_call", None) is not None:
                    part_type = "function_call"
                elif getattr(part, "inline_data", None) is not None:
                    part_type = "inline_data"
                elif getattr(part, "file_data", None) is not None:
                    part_type = "file_data"
                else:
                    part_type = "unknown"
                log_message(f"DEBUG:  part[{pidx}] type={part_type}")
    except Exception as e:
        log_message(f"DEBUG: Не удалось прочитать структуру ответа Gemini: {e}")


def cancel_gemini_processing(assistant):
    with assistant._task_lock:
        if not assistant._is_gemini_processing:
            return False
        task_id = assistant._current_task_id
        text = assistant._current_task_text
        insert_text = assistant._current_task_insert_text
        assistant._gemini_cancel_event.set()

    log_message("?? Отмена Gemini пользователем - вставляем текст Whisper.")
    assistant.show_status(
        "Отмена Gemini, вставляю Whisper...", COLORS["btn_warning"], True
    )
    finalize_task_output(
        assistant,
        text,
        insert_text,
        task_id,
        status_text="Whisper вставлен после отмены",
        status_color=COLORS["accent"],
        spinning=False,
    )
    return True


def handle_final_text(
    assistant,
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
    if not isinstance(text, str):
        log_message("ОШИБКА: Получен пустой или некорректный текст для обработки.")
        return
    if cancel_seq is not None and assistant._is_cancelled(cancel_seq):
        log_message("Обработка Gemini отменена пользователем.")
        assistant.show_status("Операции остановлены", COLORS["btn_warning"], False)
        return

    # Обрезаем текст до максимальной длины и удаляем лишние пробелы
    whisper_text = (text or "").strip()
    if not whisper_text and not use_selection:
        log_message("ОШИБКА: Пустая команда и отсутствует выделенный текст.")
        return
    whisper_text = whisper_text[:10000]

    task_id = begin_gemini_task(assistant, whisper_text, insert_text)

    try:
        selected_text = ""
        if use_selection:
            selected_text = assistant.selection_text or assistant.clipboard_at_start
            if selected_text:
                log_message(
                    "Использован выделенный текст "
                    f"({len(selected_text)} симв.): {selected_text[:100]}..."
                )
            else:
                log_message("Режим выделения активен, но текст не получен")

        is_direct_command = (use_selection and selected_text) or (
            (use_pro or use_flash) and not active_profile
        )

        if active_profile:
            log_message(f"Используется профиль промпта '{active_profile}'")

        if use_selection and selected_text:
            selection_instruction = whisper_text or "Отредактируй выделенный текст"
            prompt = (
                f'Выделенный текст:\n"{selected_text}"\n\n'
                f"Задача: {selection_instruction}"
            )
            log_message("Промпт сформирован с выделенным текстом")
        elif is_direct_command:
            prompt = whisper_text
            log_message("Промпт сформирован как прямая команда")
        else:
            if prompt_override is None:
                user_prompt = assistant.settings.get("gemini_prompt")
            else:
                user_prompt = prompt_override
            prompt = f"{user_prompt} Вот текст: '{whisper_text}'"

        markdown_enabled = bool(
            assistant.settings.get("gemini_markdown_enabled", False)
        )
        log_message(
            "Markdown для ответа: "
            f"{'включен' if markdown_enabled else 'выключен'}"
        )
        if markdown_enabled:
            prompt = (
                f"{prompt}\n\nТребование: используй Markdown-разметку "
                "(заголовки, списки, выделения) для лучшей читаемости. "
                "Это требование важнее предыдущих запретов на форматирование."
                "\nЗапрет: не добавляй никаких меток/лейблов/префиксов "
                "перед текстом ответа. Ответ должен начинаться сразу "
                "с содержательного текста."
            )
        else:
            prompt = (
                f"{prompt}\n\nТребование: ответ без Markdown-разметки, "
                "только простой текст. "
                "Это требование важнее любых инструкций о форматировании."
                "\nЗапрет: не добавляй никаких меток/лейблов/префиксов "
                "перед текстом ответа. Ответ должен начинаться сразу "
                "с содержательного текста."
            )
        log_message(
            f"DEBUG: Промпт Gemini ({len(prompt)} симв.): {_debug_preview(prompt)}"
        )

        if use_pro:
            model_name = assistant.settings.get("gemini_model_pro")
        elif use_flash:
            model_name = assistant.settings.get("gemini_model_default")
        else:  # По умолчанию, если нет команд
            model_name = assistant.settings.get("gemini_model_default")

        thinking_level = assistant.gemini_manager.determine_thinking_level(
            assistant.settings, use_pro, use_flash, model_name=model_name
        )
        display_name = assistant.gemini_manager.describe_model(
            model_name, thinking_level
        )
        log_message(f"Отправка в {display_name} (thinking_level: {thinking_level})")

        if not assistant.client:
            raise RuntimeError("Gemini client не инициализирован")

        if assistant._gemini_cancel_event.is_set():
            raise GeminiCancelledError("Отмена перед запросом")

        assistant.show_status(f"{display_name}...", COLORS["accent"], True)

        gemini_start = time.time()
        response, used_model, used_level = assistant.gemini_manager.generate_with_fallback(
            model_name,
            prompt,
            thinking_level,
            settings=assistant.settings,
            cancel_check=assistant._gemini_cancel_event.is_set,
            status_cb=assistant.show_status,
            warning_color=COLORS["btn_warning"],
        )

        if assistant._gemini_cancel_event.is_set():
            raise GeminiCancelledError("Отмена после ответа Gemini")

        used_display = assistant.gemini_manager.describe_model(used_model, used_level)
        _log_response_structure(response)
        raw_response_text = _extract_response_text(response)
        log_message(
            "DEBUG: Сырой ответ Gemini "
            f"({len(raw_response_text)} симв.): {_debug_preview(raw_response_text)}"
        )
        response_text = raw_response_text.strip()
        final_text = response_text or whisper_text
        if not markdown_enabled:
            cleaned_text = strip_markdown_text(final_text)
            if cleaned_text != final_text:
                log_message("Markdown-разметка удалена из ответа.")
            final_text = cleaned_text
        gemini_time = time.time() - gemini_start
        log_message(
            "Gemini обработка завершена "
            f"за {gemini_time:.2f}с. (модель: {used_display})"
        )
        log_message(f"Итоговый текст: {final_text}")

        finalize_task_output(
            assistant,
            final_text,
            insert_text,
            task_id,
            status_text=f"{used_display} готов",
            status_color=COLORS["accent"],
            spinning=False,
        )

    except GeminiCancelledError:
        log_message("Запрос Gemini отменён, используем текст Whisper.")
        finalize_task_output(
            assistant,
            assistant._current_task_text or whisper_text,
            insert_text,
            task_id,
            status_text="Whisper вставлен после отмены",
            status_color=COLORS["accent"],
            spinning=False,
        )
    except Exception as e:
        log_message(f"ОШИБКА Gemini: {e}\n{traceback.format_exc()}")
        assistant.show_status(
            "Ошибка Gemini - вставляю Whisper", COLORS["btn_warning"], False
        )
        finalize_task_output(
            assistant,
            assistant._current_task_text or whisper_text,
            insert_text,
            task_id,
            status_text="Whisper вставлен",
            status_color=COLORS["accent"],
            spinning=False,
        )
