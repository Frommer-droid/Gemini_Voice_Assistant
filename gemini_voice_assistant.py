# -*- coding: utf-8 -*-
"""
Gemini Voice Assistant с автоматическим распознаванием речи через Faster Whisper
и улучшением текста через Google Gemini.

"""

# Подавление предупреждений
import warnings

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

import os
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from app.speech import onnxruntime_preload as _onnxruntime_preload
_onnxruntime_preload.preload_onnxruntime()

import threading
import sys
import multiprocessing
import traceback

from app.core.app_config import APP_VERSION, COLORS
from app.core.voice_assistant import VoiceAssistant
from app.ui.main_window import ModernWindow
from app.ui.styles import apply_global_styles
from app.utils.logging_utils import log_message, log_separator

from PySide6.QtWidgets import QApplication

def main():
    try:
        log_separator()
        log_message(f"Gemini Voice Assistant v{APP_VERSION} запущен")
        log_message(f"Исполняемый файл: {sys.executable}")
        log_separator()

        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        apply_global_styles(app, COLORS)

        assistant = VoiceAssistant()

        _window = ModernWindow(assistant)

        assistant_thread = threading.Thread(target=assistant.run, daemon=True)
        assistant_thread.start()

        # Окно уже показано в __init__ ModernWindow

        sys.exit(app.exec())

    except Exception as e:
        log_message(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        log_message(traceback.format_exc())
        log_separator()

        print(f"Критическая ошибка: {e}")
        print(traceback.format_exc())
        input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
