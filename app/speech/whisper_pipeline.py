# -*- coding: utf-8 -*-
"""Аудио и Whisper-пайплайн: запись, VAD и обработка сегментов."""

import os
import re
import threading
import time
import traceback

import numpy as np
import pyaudio
import pyperclip

from app.core.app_config import COLORS, WHISPER_MODELS_DIR
from app.utils.logging_utils import log_message, log_separator


def setup_audio(assistant) -> None:
    assistant.audio = pyaudio.PyAudio()
    assistant.sample_rate = 16000
    assistant.chunk_size = 1024
    assistant.channels = 1


def setup_whisper(assistant, model_name=None):
    if model_name is None:
        model_name = assistant.settings.get("whisper_model")
    return assistant.whisper_engine.setup(
        model_name, status_cb=assistant.show_status, colors=COLORS
    )


def start_recording(assistant, continuous=False, source=None) -> None:
    if assistant.is_recording or assistant.is_continuous_recording:
        return

    if assistant._cancel_pending.is_set():
        assistant._cancel_pending.clear()

    assistant._recording_hotkey_source = source

    if continuous:
        assistant.is_continuous_recording = True
        log_separator()
        log_message("Запуск НЕПРЕРЫВНОЙ диктовки")
    else:
        assistant.is_recording = True
        log_separator()
        log_message("Запуск ОБЫЧНОЙ диктовки")

    assistant.start_time = time.time()

    try:
        assistant.clipboard_at_start = pyperclip.paste()
        assistant.selection_text = assistant.clipboard_at_start
        log_message(
            "Сохранен буфер обмена "
            f"({len(assistant.clipboard_at_start)} симв.): "
            f"{assistant.clipboard_at_start[:100]}..."
        )
        if assistant.selection_text:
            log_message(
                "Используем текст из буфера "
                f"({len(assistant.selection_text)} симв.) для режима 'Выделить'"
            )
    except Exception as e:
        assistant.clipboard_at_start = ""
        assistant.selection_text = ""
        log_message(f"Ошибка сохранения буфера обмена: {e}")

    assistant.play_sound("start")
    assistant.show_status("Идет запись...", COLORS["btn_warning"], True)
    if assistant.ui_signals:
        assistant.ui_signals.request_show_window.emit()
        assistant.ui_signals.recording_state_changed.emit(True)

    threading.Thread(
        target=assistant._record_audio, args=(continuous,), daemon=True
    ).start()


def stop_recording(assistant, continuous=False) -> None:
    if continuous:
        if not assistant.is_continuous_recording:
            return
        assistant.is_continuous_recording = False
        log_message("Остановка непрерывной диктовки")
    else:
        if not assistant.is_recording:
            return
        assistant.is_recording = False
        log_message("Остановка обычной диктовки")

    assistant._recording_hotkey_source = None
    assistant.play_sound("stop")
    if assistant.ui_signals:
        assistant.ui_signals.recording_state_changed.emit(False)


def record_audio(assistant, continuous=False) -> None:
    # ИСПРАВЛЕНИЕ 1: Проверяем что модель Whisper загружена
    if not assistant.whisper_engine.is_ready():
        log_message("ОШИБКА: Модель Whisper не загружена!")
        log_message(
            "Выбранная модель в настройках: "
            f"{assistant.settings.get('whisper_model')}"
        )
        assistant.show_status(
            "Загрузите модель в настройках!", COLORS["btn_warning"], False
        )
        assistant.play_sound("error")

        if continuous:
            assistant.is_continuous_recording = False
        else:
            assistant.is_recording = False

        threading.Timer(
            3.0,
            lambda: assistant.show_status("Готов к работе", COLORS["accent"], False),
        ).start()
        return

    # ДОБАВИТЬ после проверки (НОВАЯ СЕКЦИЯ):
    # Логируем информацию о активной модели
    active_model = assistant.settings.get("whisper_model", "unknown")
    log_message(f"Используется модель Whisper: {active_model}")
    log_message(
        f"Whisper объект инициализирован: {assistant.whisper_engine.is_ready()}"
    )

    # ИСПРАВЛЕНИЕ 2: Правильная обработка микрофона "По умолчанию"
    mic_index = assistant.settings.get("microphone_index")

    if mic_index is None or mic_index == -1:
        try:
            default_info = assistant.audio.get_default_input_device_info()
            mic_index = default_info["index"]
            log_message(
                "Используется микрофон по умолчанию: "
                f"{default_info['name']} (индекс {mic_index})"
            )
        except Exception as e:
            log_message(
                "Не удалось получить дефолтный микрофон: "
                f"{e}. Используем None."
            )
            mic_index = None
    else:
        log_message(f"Используется выбранный микрофон: индекс {mic_index}")

    try:
        stream = assistant.audio.open(
            format=pyaudio.paInt16,
            channels=assistant.channels,
            rate=assistant.sample_rate,
            input=True,
            input_device_index=mic_index,
            frames_per_buffer=assistant.chunk_size,
        )
    except (OSError, ValueError) as e:
        log_message(f"ОШИБКА: Микрофон недоступен: {e}")
        assistant.show_status("Микрофон не подключен", COLORS["btn_warning"], False)
        if continuous:
            assistant.is_continuous_recording = False
        else:
            assistant.is_recording = False
        return

    if continuous:
        assistant.audio_buffer.clear()

    frames = []
    max_level = 0

    while assistant.is_recording or assistant.is_continuous_recording:
        try:
            data = stream.read(assistant.chunk_size, exception_on_overflow=False)
            frames.append(data)
            audio_np = np.frombuffer(data, dtype=np.int16)
            level = np.abs(audio_np).mean()
            max_level = max(max_level, level)
            assistant.update_volume_indicator(level)

            if (
                continuous
                and len(frames) * assistant.chunk_size / assistant.sample_rate >= 15
            ):
                audio_data = b"".join(frames)
                audio_np_segment = (
                    np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                    / 32768.0
                )
                threading.Thread(
                    target=assistant._process_continuous_segment,
                    args=(audio_np_segment,),
                    daemon=True,
                ).start()

                overlap_frames = int(
                    5 * assistant.sample_rate / assistant.chunk_size
                )
                frames = frames[-overlap_frames:]

        except Exception as e:
            log_message(f"Ошибка чтения аудио: {e}")
            break

    stream.stop_stream()
    stream.close()
    log_message(f"Аудио поток закрыт. Записано фреймов: {len(frames)}")

    if frames:
        audio_data = b"".join(frames)
        audio_samples = np.frombuffer(audio_data, dtype=np.int16)

        if assistant._should_skip_silence(audio_samples, max_level):
            log_message(f"Silence guard: skip chunk (level {max_level:.1f})")
            assistant.show_status(
                "Тишина - запись отменена", COLORS["btn_warning"], False
            )
            assistant.play_sound("error")
            if assistant.ui_signals:
                assistant.ui_signals.request_hide_window.emit()
            threading.Timer(
                2.0,
                lambda: assistant.show_status(
                    "Готов к работе", COLORS["accent"], False
                ),
            ).start()
            return

        log_message(f"Максимальный уровень записи: {max_level}")
        audio_np = audio_samples.astype(np.float32) / 32768.0

        if continuous:
            assistant._process_audio_whisper(audio_np, is_final_segment=True)
        else:
            assistant._process_audio_whisper(audio_np, is_final_segment=False)
    else:
        log_message("ОШИБКА: Нет записанных аудио данных")
        assistant.show_status("Нет аудио", COLORS["btn_warning"], False)
        assistant.play_sound("error")
        if assistant.ui_signals:
            assistant.ui_signals.request_hide_window.emit()
        threading.Timer(
            2.0,
            lambda: assistant.show_status("Готов к работе", COLORS["accent"], False),
        ).start()


def should_skip_silence(assistant, audio_samples, chunk_peak) -> bool:
    silence_enabled = assistant.settings.get(
        "silence_detection_enabled",
        assistant.settings.get("audio_quality_check", False),
    )
    if not silence_enabled or audio_samples.size == 0:
        return False

    min_level = assistant.settings.get("min_audio_level", 500)
    min_duration = max(
        0.1, assistant.settings.get("silence_duration_ms", 600) / 1000.0
    )
    duration = len(audio_samples) / float(assistant.sample_rate or 1)
    avg_level = float(np.abs(audio_samples).mean())
    effective_level = max(avg_level, chunk_peak)

    if duration >= min_duration and effective_level < min_level:
        log_message(
            "Silence guard triggered: "
            f"{duration:.2f}s at level {effective_level:.1f} (< {min_level})"
        )
        return True

    return False


def process_continuous_segment(assistant, audio_np) -> None:
    """Обрабатывает сегмент в непрерывном режиме, только добавляя в буфер."""
    try:
        if assistant._cancel_pending.is_set():
            log_message("Сегмент пропущен из-за отмены пользователя.")
            return
        log_message("Обработка промежуточного сегмента...")
        segments, _ = assistant.whisper_engine.transcribe(audio_np, assistant.settings)
        text = " ".join([s.text for s in segments]).strip()
        if text:
            # Ограничение размера буфера для предотвращения утечки памяти
            max_buffer_size = 100
            if len(assistant.audio_buffer) >= max_buffer_size:
                log_message(
                    "ПРЕДУПРЕЖДЕНИЕ: Буфер непрерывной записи "
                    f"достиг предела ({max_buffer_size}). Старый сегмент удален."
                )
                assistant.audio_buffer.pop(0)

            assistant.audio_buffer.append(text)
            log_message(
                f"Добавлен сегмент в буфер ({len(text)} симв.): {text[:100]}..."
            )
    except Exception as e:
        log_message(f"Ошибка обработки сегмента: {e}\n{traceback.format_exc()}")


def process_audio_whisper(assistant, audio_np, is_final_segment=False) -> None:
    """Финальная обработка аудио, распознавание и вызов _handle_final_text."""
    if assistant._cancel_pending.is_set():
        log_message("Whisper обработка пропущена из-за отмены пользователя.")
        assistant.show_status("Операции остановлены", COLORS["btn_warning"], False)
        return
    assistant.show_status("Обработка...", COLORS["accent"], True)
    cancel_seq = assistant._get_cancel_seq()
    try:
        model_name = assistant.settings.get("whisper_model", "unknown")
        model_path = os.path.join(
            WHISPER_MODELS_DIR, f"faster-whisper-{model_name}"
        )

        if not assistant.whisper_engine.is_ready():
            log_message(
                "Whisper не активен, пробую загрузить модель перед распознаванием."
            )
            if not assistant.setup_whisper(model_name):
                log_message("Whisper не активирован, распознавание отменено.")
                assistant.show_status(
                    "Модель Whisper не активна", COLORS["btn_warning"], False
                )
                assistant.play_sound("error")
                threading.Timer(
                    2.0,
                    lambda: assistant.show_status(
                        "Готов к работе", COLORS["accent"], False
                    ),
                ).start()
                return

        log_message("==================== WHISPER ОБРАБОТКА ====================")
        log_message(f"Выбранная модель: {model_name}")
        log_message(f"Путь к модели: {model_path}")
        log_message(f"Модель активна: {assistant.whisper_engine.is_ready()}")
        log_message("Начало распознавания...")
        whisper_start = time.time()

        segments, _ = assistant.whisper_engine.transcribe(audio_np, assistant.settings)
        text = " ".join([s.text for s in segments]).strip()

        if assistant._is_cancelled(cancel_seq):
            log_message("Whisper обработка отменена пользователем.")
            assistant.show_status("Операции остановлены", COLORS["btn_warning"], False)
            return

        whisper_time = time.time() - whisper_start
        log_message(
            "Распознавание завершено "
            f"за {whisper_time:.2f}с (модель: {model_name})"
        )
        log_message("==========================================================")

        if is_final_segment and text:
            assistant.audio_buffer.append(text)

        final_text = text
        if is_final_segment and assistant.audio_buffer:
            final_text = " ".join(assistant.audio_buffer).strip()
            log_message(
                "Собран полный текст из "
                f"{len(assistant.audio_buffer)} сегментов для Gemini "
                f"({len(final_text)} симв.)"
            )

        # --- ПАРСИНГ И ОБРАБОТКА ПРОФИЛЯ (ПЕРЕМЕЩЕНО ВЫШЕ) ---
        if final_text:
            if assistant._is_cancelled(cancel_seq):
                log_message("Обработка команды отменена пользователем.")
                assistant.show_status("Операции остановлены", COLORS["btn_warning"], False)
                return
            log_message(
                f"Распознанный текст ({len(final_text)} символов): {final_text}"
            )

            # Команды проверяем сразу, чтобы "открой/найди/запусти" работали всегда.
            command_text = text if is_final_segment and text else final_text
            if command_text:
                if assistant.command_router.handle_website_command(command_text):
                    return
                if assistant.command_router.handle_launch_command(command_text):
                    return
                if assistant.command_router.handle_everything_search(command_text):
                    return

            raw_words = final_text.strip().split()
            tokens = [
                (re.sub(r"[^\w]", "", w, flags=re.UNICODE).lower(), w)
                for w in raw_words
            ]

            def _next_meaningful(start_index):
                """Возвращает индекс и нормализованное слово, пропуская пустые токены."""
                for idx in range(start_index, len(tokens)):
                    norm, _ = tokens[idx]
                    if norm:
                        return idx, norm
                return None, ""

            first_idx, first_word = _next_meaningful(0)
            if first_idx is None:
                log_message("ОШИБКА: не удалось найти первое слово после очистки.")
                assistant.show_status("Не распознано", COLORS["btn_warning"], False)
                return

            use_pro_model = False
            use_flash_model = False
            use_selected_text = False
            words_to_skip = 0
            active_profile_name = None
            prompt_override = None
            direct_model_trigger = False

            pro_word = (assistant.settings.get("pro_word", "про") or "про").strip().lower()
            flash_word = (
                (assistant.settings.get("flash_word", "флеш") or "флеш")
                .strip()
                .lower()
            )
            selection_word = (
                (assistant.settings.get("selection_word", "выделить") or "выделить")
                .strip()
                .lower()
            )

            prompts = assistant.settings.get("gemini_prompts", {})
            if not isinstance(prompts, dict):
                prompts = {}
            profile_lookup = {name.strip().lower(): name for name in prompts.keys()}
            dictation_profile_name = profile_lookup.get("диктовка")
            selected_profile_setting = (
                assistant.settings.get("gemini_selected_prompt") or ""
            ).strip().lower()
            selected_profile_name = profile_lookup.get(selected_profile_setting)

            # --- Обработка выделения (отдельный режим) ---
            if first_word == selection_word:
                use_selected_text = True
                words_to_skip = first_idx + 1
                next_idx, next_word = _next_meaningful(words_to_skip)
                if next_idx is not None and next_word:
                    if next_word == pro_word:
                        use_pro_model = True
                        direct_model_trigger = True
                        words_to_skip = next_idx + 1
                        log_message("Включено условие 'Выделить Pro'")
                    elif next_word == flash_word:
                        use_flash_model = True
                        use_pro_model = False
                        direct_model_trigger = True
                        words_to_skip = next_idx + 1
                        log_message("Включено условие 'Выделить Flash'")
                if words_to_skip == first_idx + 1:  # только слово выделения
                    use_pro_model = True
                    log_message("Включено условие 'Выделить' (по умолчанию Pro)")
            else:
                # --- Обработка профиля промпта ---
                profile_match = profile_lookup.get(first_word)
                if profile_match:
                    active_profile_name = profile_match
                    prompt_override = prompts.get(profile_match, "")
                    words_to_skip = first_idx + 1

                if active_profile_name:
                    profile_lower = active_profile_name.strip().lower()
                    if profile_lower == "диктовка":
                        use_flash_model = True
                        use_pro_model = False
                        log_message(
                            "Профиль 'Диктовка' активирован  модель Flash по умолчанию"
                        )
                    elif profile_lower == "ассистент":
                        use_pro_model = True
                        log_message(
                            "Профиль 'Ассистент' активирован  модель Pro по умолчанию"
                        )

                    # Ищем следующее значимое слово (пропуская знаки препинания) для выбора модели
                    next_idx, next_word = _next_meaningful(words_to_skip)
                    if next_idx is not None and next_word:
                        if next_word == pro_word:
                            if profile_lower == "диктовка":
                                log_message(
                                    "Профиль 'Диктовка' всегда использует Flash, команда Pro проигнорирована"
                                )
                            else:
                                use_pro_model = True
                                use_flash_model = False
                                direct_model_trigger = True
                                log_message(
                                    f"Профиль '{active_profile_name}' с командой Pro"
                                )
                            words_to_skip = next_idx + 1
                        elif next_word == flash_word:
                            use_flash_model = True
                            use_pro_model = False
                            direct_model_trigger = True
                            words_to_skip = next_idx + 1
                            log_message(
                                f"Профиль '{active_profile_name}' с командой Flash"
                            )

                    if profile_lower == "диктовка":
                        use_flash_model = True
                        use_pro_model = False
                else:
                    # --- Прямые переключатели без профиля ---
                    if first_word == pro_word:
                        use_pro_model = True
                        direct_model_trigger = True
                        words_to_skip = first_idx + 1
                        log_message("Включено условие Gemini Pro")
                    elif first_word == flash_word:
                        use_flash_model = True
                        direct_model_trigger = True
                        words_to_skip = first_idx + 1
                        log_message("Включено условие Gemini Flash")

            if (
                not use_selected_text
                and not active_profile_name
                and not direct_model_trigger
            ):
                if selected_profile_name:
                    active_profile_name = selected_profile_name
                    prompt_override = prompts.get(selected_profile_name, "")
                    profile_lower = active_profile_name.strip().lower()
                    if profile_lower == "диктовка":
                        use_flash_model = True
                        use_pro_model = False
                    elif profile_lower == "ассистент":
                        use_pro_model = True
                    log_message(f"Режим по умолчанию: профиль '{active_profile_name}'")
                elif dictation_profile_name:
                    active_profile_name = dictation_profile_name
                    prompt_override = prompts.get(dictation_profile_name, "")
                    use_flash_model = True
                    use_pro_model = False
                    log_message("Режим диктовки по умолчанию (профиль не выбран)")
                else:
                    log_message(
                        "Выбранный профиль не найден, использую текущий промпт"
                    )

            if words_to_skip > 0:
                final_text = " ".join(raw_words[words_to_skip:])

            assistant._handle_final_text(
                final_text,
                insert_text=True,
                use_pro=use_pro_model,
                use_flash=use_flash_model,
                use_selection=use_selected_text,
                active_profile=active_profile_name,
                prompt_override=prompt_override,
                cancel_seq=cancel_seq,
            )
        else:
            log_message("Ошибка: Whisper вернул пустой результат")
            assistant.show_status("Не распознано", COLORS["btn_warning"], False)
            assistant.play_sound("error")
            threading.Timer(
                2.0,
                lambda: assistant.show_status(
                    "Готово к записи", COLORS["accent"], False
                ),
            ).start()
    except Exception as e:
        log_message(
            "КРИТИЧЕСКАЯ ОШИБКА обработки Whisper: "
            f"{e}\n{traceback.format_exc()}"
        )
        assistant.show_status("Ошибка Whisper", COLORS["btn_warning"], False)
        assistant.play_sound("error")
        threading.Timer(
            2.0,
            lambda: assistant.show_status("Готов к работе", COLORS["accent"], False),
        ).start()
