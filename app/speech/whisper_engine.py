# -*- coding: utf-8 -*-
import os
import traceback
from typing import Optional

from app.core.app_config import LANGUAGE
from app.utils.logging_utils import log_message, log_separator
from app.speech.onnxruntime_preload import (
    get_prepare_info,
    get_preload_error,
    get_preload_dll_errors,
    preload_onnxruntime,
    was_kmp_workaround_used,
)


class WhisperEngine:
    def __init__(self, models_dir: str, language: str = LANGUAGE, log_func=log_message):
        self.models_dir = models_dir
        self.language = language
        self.log = log_func
        self.whisper = None
        self._vad_available = None
        self._whisper_model_class = None

    def is_ready(self) -> bool:
        return self.whisper is not None

    def setup(self, model_name: str, status_cb=None, colors: Optional[dict] = None) -> bool:
        if not model_name:
            return False

        if status_cb and colors:
            status_cb(f"Загрузка {model_name}...", colors["accent"], True)

        model_path = os.path.join(self.models_dir, f"faster-whisper-{model_name}")

        # Проверка наличия модели
        if not os.path.isdir(model_path):
            self.log(f"ОШИБКА: Папка модели не найдена: {model_path}")
            if status_cb and colors:
                status_cb(
                    f"Модель {model_name} не найдена", colors["btn_warning"], False
                )
            return False

        try:
            log_separator()
            self.log(f"Загрузка Whisper ({model_name})...")

            self._ensure_whisper_imported()
            self.whisper = self._whisper_model_class(
                model_path,
                device="cpu",
                compute_type="int8",
            )

            self.log(f"Whisper {model_name} успешно загружен из {model_path}")
            log_separator()
            if status_cb and colors:
                status_cb(f"Модель {model_name} активна", colors["accent"], False)
            return True
        except Exception as e:
            self.log(f"КРИТИЧЕСКАЯ ОШИБКА загрузки Whisper: {e}")
            self.log(traceback.format_exc())
            log_separator()
            if status_cb and colors:
                status_cb(f"Ошибка загрузки {model_name}", colors["btn_warning"], False)
            return False

    def is_model_downloaded(self, model_name: str) -> bool:
        """Проверяет наличие папки модели"""
        try:
            model_path = os.path.join(self.models_dir, f"faster-whisper-{model_name}")

            if not os.path.isdir(model_path):
                self.log(f"Папка модели не найдена: {model_path}")
                return False

            self.log(f"Модель '{model_name}' найдена в {model_path}")
            return True

        except Exception as e:
            self.log(f"Ошибка проверки модели '{model_name}': {e}")
            return False

    def build_options(self, settings: dict) -> dict:
        options = {
            "language": self.language,
            "no_speech_threshold": settings.get("no_speech_threshold", 0.85),
            "log_prob_threshold": settings.get("logprob_threshold", -1.2),
            "condition_on_previous_text": settings.get("condition_on_prev_text", False),
            "hallucination_silence_threshold": settings.get(
                "hallucination_silence", 2.0
            ),
        }
        vad_enabled = settings.get("whisper_vad_enabled", True)
        if vad_enabled and not self._check_vad_support():
            vad_enabled = False
        options["vad_filter"] = vad_enabled
        if vad_enabled:
            options["vad_parameters"] = {
                "min_speech_duration_ms": settings.get("vad_min_speech_ms", 250),
                "max_speech_duration_s": settings.get("vad_max_speech_s", 14),
                "min_silence_duration_ms": settings.get("vad_min_silence_ms", 600),
                "speech_pad_ms": settings.get("vad_pad_ms", 200),
            }
        return options

    def transcribe(self, audio_np, settings: dict):
        if not self.whisper:
            raise RuntimeError("Whisper модель не инициализирована")
        options = self.build_options(settings)
        try:
            return self.whisper.transcribe(audio_np, **options)
        except RuntimeError as e:
            if "VAD filter requires the onnxruntime package" not in str(e):
                raise
            self.log(
                "ONNXRuntime недоступен. Отключаю VAD и повторяю распознавание."
            )
            options["vad_filter"] = False
            options.pop("vad_parameters", None)
            return self.whisper.transcribe(audio_np, **options)

    def _check_vad_support(self) -> bool:
        if self._vad_available is not None:
            return self._vad_available
        preload_ok = preload_onnxruntime(self.log, force=True)
        if preload_ok:
            try:
                import onnxruntime as ort

                self._vad_available = True
                msg = (
                    f"ONNXRuntime доступен (версия {ort.__version__}). VAD активен."
                )
                if was_kmp_workaround_used():
                    msg += " Использован KMP_DUPLICATE_LIB_OK=TRUE."
                self.log(msg)
                return True
            except Exception as e:
                first_error = e
        else:
            first_error = get_preload_error()

        info = get_prepare_info()
        if info:
            details = (
                "ONNXRuntime пути: "
                f"package={info.get('package_dir')}, "
                f"capi={info.get('capi_dir')}, "
                f"PATH_есть={info.get('path_present')}, "
                f"PATH_добавлен={info.get('path_added')}, "
                f"add_dll_directory={info.get('dll_directory_added')}"
            )
            if info.get("meipass"):
                details += f", _MEIPASS={info.get('meipass')}"
            self.log(details)
        dll_errors = get_preload_dll_errors()
        if dll_errors:
            for dll_path, err in dll_errors:
                self.log(
                    f"ONNXRuntime DLL не загрузился: {dll_path}. Причина: {err}"
                )
        if was_kmp_workaround_used():
            self.log(
                "ONNXRuntime: применен KMP_DUPLICATE_LIB_OK=TRUE "
                "для повторной попытки."
            )
        self._vad_available = False
        reason = first_error if first_error else "неизвестная ошибка"
        self.log(
            "ONNXRuntime недоступен. VAD будет отключен. "
            f"Причина: {reason}"
        )
        return self._vad_available

    def _ensure_whisper_imported(self) -> None:
        if self._whisper_model_class is not None:
            return
        # Пытаемся загрузить onnxruntime ДО faster_whisper, чтобы избежать DLL-конфликта.
        self._check_vad_support()
        from faster_whisper import WhisperModel

        self._whisper_model_class = WhisperModel
