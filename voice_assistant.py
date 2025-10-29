# -*- coding: utf-8 -*-
"""
Voice Assistant с автоматическим распознаванием речи через Whisper
и улучшением текста через Google Gemini.

Финальная версия с интерфейсом на PySide6.
ИСПРАВЛЕННАЯ ВЕРСИЯ - готова к компиляции PyInstaller.
"""

# Подавление предупреждений
import warnings

warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

import threading
import time
import datetime
import logging
from logging.handlers import RotatingFileHandler
import os
import subprocess
import json
import sys
import ctypes
import multiprocessing
import socket
import re
from collections import deque
import winsound
import webbrowser
import numpy as np
import pyperclip
from pynput import keyboard
import pyaudio
import sounddevice as sd
import winreg
import traceback

from google import genai
from google.genai import types
from faster_whisper import WhisperModel

# Импорт VLESS VPN менеджера
from vless_manager import VLESSManager

from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QFrame,
    QSystemTrayIcon,
    QMenu,
    QSizePolicy,
    QTabWidget,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QRadioButton,
    QGroupBox,
    QSpinBox,
    QTextEdit,
    QDialog,
    QMessageBox,
    QSizeGrip,
    QSplitter,
    QStyledItemDelegate,
)
from PySide6.QtGui import QIcon, QAction, QMouseEvent, QPainter, QColor, QPixmap, QFont
from PySide6.QtCore import (
    Qt,
    QTimer,
    QSize,
    QPropertyAnimation,
    QEasingCurve,
    Signal,
    QObject,
    QRect,
    QPoint,
    QThread,
)


class NoElidingDelegate(QStyledItemDelegate):
    """
    Кастомный делегат для отключения обрезания текста в QComboBox.
    Показывает полный текст без сокращений.
    """

    def sizeHint(self, option, index):
        # Получаем оригинальный размер
        size = super().sizeHint(option, index)
        # Увеличиваем ширину чтобы вместить полный текст
        text = index.data()
        if text:
            fm = option.fontMetrics
            text_width = fm.horizontalAdvance(text) + 40  # +40 для отступов
            size.setWidth(max(size.width(), text_width))
        return size

    def paint(self, painter, option, index):
        # Отключаем eliding при отрисовке
        opt = option
        opt.textElideMode = Qt.TextElideMode.ElideNone
        super().paint(painter, opt, index)


# --- Исправление для PyInstaller ---
if getattr(sys, "frozen", False):
    import certifi

    os.environ["SSL_CERT_FILE"] = certifi.where()

    if hasattr(sys, "_MEIPASS"):
        os.environ["TMPDIR"] = sys._MEIPASS


def get_executable_path():
    """Возвращает путь к exe-файлу приложения"""
    if getattr(sys, "frozen", False):
        exe_path = sys.executable
        if "_internal" in exe_path or "_MEI" in exe_path:
            possible_paths = [
                os.path.join(
                    os.path.dirname(os.path.dirname(exe_path)), "VoiceAssistant.exe"
                ),
                os.path.join(os.path.dirname(exe_path), "VoiceAssistant.exe"),
            ]
            for path in possible_paths:
                if os.path.exists(path):
                    return os.path.normpath(path)
        return os.path.normpath(exe_path)
    else:
        return os.path.normpath(os.path.abspath(sys.argv[0]))


def get_exe_directory():
    """Возвращает путь к папке с exe-файлом"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.abspath(__file__))


def get_models_directory():
    """Возвращает путь к папке с моделями Whisper (всегда рядом с exe)"""
    exe_dir = get_exe_directory()
    models_dir = os.path.join(exe_dir, "whisper_models")

    if not os.path.exists(models_dir):
        try:
            os.makedirs(models_dir)
            print(f"Создана папка для моделей: {models_dir}")
        except Exception as e:
            print(f"Ошибка создания папки моделей: {e}")

    return models_dir


def resource_path(relative_path):
    """Улучшенный поиск ресурсов"""
    exe_dir = get_exe_directory()
    path_in_exe_dir = os.path.join(exe_dir, relative_path)
    if os.path.exists(path_in_exe_dir):
        return path_in_exe_dir

    try:
        base_path = sys._MEIPASS
        path_in_meipass = os.path.join(base_path, relative_path)
        if os.path.exists(path_in_meipass):
            return path_in_meipass
    except AttributeError:
        pass

    return path_in_exe_dir


# --- Установка рабочей директории ---
if getattr(sys, "frozen", False):
    exe_dir = os.path.dirname(sys.executable)
    os.chdir(exe_dir)

    with open("startup_log.txt", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.datetime.now()}] === ЗАПУСК ПРИЛОЖЕНИЯ ===\n")
        f.write(f"sys.executable: {sys.executable}\n")
        f.write(f"sys.argv[0]: {sys.argv[0]}\n")
        f.write(f"EXE_DIR: {exe_dir}\n")
        f.write(f"MODELS_DIR: {get_models_directory()}\n")
        f.write(f"os.getcwd(): {os.getcwd()}\n")
        f.write(f"sys.frozen: {getattr(sys, 'frozen', False)}\n\n")


# --- Конфигурация ---
EXE_DIR = get_exe_directory()
HISTORY_FILE = os.path.join(EXE_DIR, "speech_history.txt")
LOG_FILE = os.path.join(EXE_DIR, "voice_assistant.log")
SETTINGS_FILE = os.path.join(EXE_DIR, "settings.json")
WHISPER_MODELS_DIR = get_models_directory()


GEMINI_MODEL = "gemini-2.5-flash"
HOTKEY_COMBO = {keyboard.Key.cmd, keyboard.Key.shift}
CONTINUOUS_HOTKEY = keyboard.Key.f1
LANGUAGE = "ru"

DEFAULT_SETTINGS = {
    "whisper_model": "small",
    "thinking_enabled": False,
    "proxy_enabled": False,
    "proxy_address": "127.0.0.1",
    "proxy_port": "10808",
    "sound_scheme": "Отключены",
    "audio_quality_check": False,
    "min_audio_level": 500,
    "microphone_index": 1,
    "win_shift_mode": "Обычный",
    "f1_mode": "Непрерывный",
    "autostart_enabled": False,
    "start_minimized": False,
    "compact_width": 301,
    "compact_height": 113,
    "expanded_width": 733,
    "expanded_height": 707,
    "window_pos_x": 1132,
    "window_pos_y": 40,
    "history_window_width": 1000,
    "history_window_height": 1000,
    "history_font_size": 16,
    "log_window_width": 1100,
    "log_window_height": 1000,
    "log_font_size": 16,
    "title_font_size": 16,
    "status_font_size": 12,
    "gemini_prompt": "Ты — эксперт по редактированию речи и текстов, полученных с микрофона.\nТебе даётся сырой текст.\nТвоя задача — преобразовать этот текст в чистую, отредактированную письменную версию.\nТребования:\n1. Проверь текст на грамматику, стиль, логику и ясность.\n2. Уточни фактическую корректность имён, дат, названий и терминов, используя актуальные источники в интернете.\n3. Иностранные термины и названия пиши на английском языке.\n4. Выведи только итоговый отредактированный текст — без комментариев, пояснений и форматирования вроде «исправленный вариант:».\n5. Не изменяй падежи, род и число слов.\n6. Если текст похож на вопрос, не отвечай на него, а просто обработай его как обычный текст.\n7. Если в диктовке есть неверные сведения, не исправляй их.\nЗадача: сделать текст чистым, грамотным и стилистически естественным, без искажения смысла.",
    "gemini_prompt_height": 250,
    "gemini_model_default": "gemini-2.5-flash",
    "gemini_model_pro": "gemini-2.5-pro",
    "selection_word": "выделить",
    "pro_word": "старт",
    "flash_word": "финиш",
    "gemini_api_key": "",  # ← НОВАЯ НАСТРОЙКА!
    # VLESS VPN настройки
    "vless_enabled": True,
    "vless_url": "",
    "vless_autostart": True,
    "vless_port": 10809,  # ← НОВАЯ НАСТРОЙКА!
}

COLORS = {
    "bg_main": "#17212B",
    "bg_dark": "#0E1621",
    "accent": "#3AE2CE",
    "white": "#FFFFFF",
    "btn_standard": "#4B82E5",
    "btn_warning": "#BF8255",
    "volume_bar": "#2ecc71",
    "volume_bar_low": "#e74c3c",
    "record": "#e74c3c",
    "border_grey": "#4F5B6A",
}

SOUND_SCHEMES = {
    "Стандартные": {"start": (800, 100), "stop": (400, 100), "error": (300, 200)},
    "Тихие": {"start": (600, 50), "stop": (500, 50), "error": (400, 100)},
    "Мелодичные": {"start": (1000, 150), "stop": (500, 150), "error": (300, 300)},
    "Отключены": {},
}


# --- Логирование ---
def setup_logging():
    """Настройка логирования с автоматической ротацией"""
    logger = logging.getLogger(__name__)
    logger.setLevel(logging.DEBUG)

    # ИСПРАВЛЕНО: Явно указываем UTF-8 и errors='replace'
    handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=200 * 1024,
        backupCount=1,
        encoding="utf-8",
        errors="replace",  # Добавлено: заменяет некорректные символы
    )

    # ИСПРАВЛЕНО: Форматтер с явной поддержкой Unicode
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger


def setup_history_logging():
    """Настройка логирования истории с ротацией"""
    history_logger = logging.getLogger("history")
    history_logger.setLevel(logging.INFO)

    if history_logger.hasHandlers():
        history_logger.handlers.clear()

    handler = RotatingFileHandler(
        HISTORY_FILE, maxBytes=500 * 1024, backupCount=2, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(message)s"))
    history_logger.addHandler(handler)
    return history_logger


logger = setup_logging()
history_logger = setup_history_logging()


def log_message(msg):
    """Логирование в файл"""
    try:
        logger.info(msg)
    except:
        pass


def log_separator():
    """Добавляет разделитель в лог-файл"""
    try:
        logger.info("=" * 80)
    except:
        pass


def get_microphone_list():
    """
    Возвращает список физических микрофонов, исключая виртуальные и дубликаты.
    Показывает ПОЛНЫЕ имена как в настройках Windows.
    """
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        microphones = []
        exclude_keywords = [
            "stereo mix",
            "wave out",
            "loopback",
            "what u hear",
            "wasapi",
            "kernel streaming",
            "wdm-ks",
            "wdm",
            "primary sound",
            "communications",
            "recording control",
            "volume control",
            "output",
            "speaker",
            "headphone",
            "playback",
            "render",
            "line out",
            "spdif",
            "digital output",
            "hdmi",
            "optical",
            "wave:",
            "microsoft",
            "virtual",
            "cable",
            "voicemeeter",
            "vb-audio",
            "переназначение",
            "по умолчанию",
        ]
        seen_names = set()
        for i, d in enumerate(devices):
            if d.get("max_input_channels", 0) > 0:
                device_name = d.get("name", "").lower()
                original_name = d.get("name", "")  # полное имя!
                if any(keyword in device_name for keyword in exclude_keywords):
                    continue
                hostapi = d.get("hostapi", -1)
                try:
                    hostapi_info = sd.query_hostapis(hostapi)
                    hostapi_name = hostapi_info.get("name", "").lower()
                    if "mme" not in hostapi_name:
                        continue
                except:
                    pass
                if original_name.lower() in seen_names:
                    continue
                seen_names.add(original_name.lower())

                # Показываем ПОЛНОЕ имя устройства без обработки
                display_name = original_name

                log_message(f"  Устройство: '{original_name}' → '{display_name}'")

                microphones.append((i, display_name))
        return microphones
    except Exception as e:
        print(f"Ошибка получения микрофонов: {e}")
        return []


class UiSignals(QObject):
    status_changed = Signal(str, str, bool)
    volume_changed = Signal(int)
    recording_state_changed = Signal(bool)
    history_updated = Signal()
    request_show_window = Signal()
    request_hide_window = Signal()


class LogViewerWindow(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр логов")
        self.setWindowFlags(Qt.WindowType.Window)

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

        layout.addWidget(self.text_edit)

        button_layout = QHBoxLayout()
        refresh_btn = QPushButton("Обновить")
        copy_btn = QPushButton("Копировать все")
        close_btn = QPushButton("Закрыть")

        refresh_btn.clicked.connect(self.load_logs)
        copy_btn.clicked.connect(self.copy_logs)
        close_btn.clicked.connect(self.close)

        button_layout.addWidget(refresh_btn)
        button_layout.addWidget(copy_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.load_logs()

    def load_logs(self):
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, "r", encoding="utf-8") as f:
                    self.text_edit.setPlainText(f.read())
                    cursor = self.text_edit.textCursor()
                    cursor.movePosition(cursor.MoveOperation.End)
                    self.text_edit.setTextCursor(cursor)
        except Exception as e:
            self.text_edit.setPlainText(f"Ошибка загрузки логов: {e}")

    def copy_logs(self):
        pyperclip.copy(self.text_edit.toPlainText())


class HistoryViewerWindow(QDialog):
    def __init__(self, history_text, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Просмотр записи")
        self.setWindowFlags(Qt.WindowType.Window)

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setPlainText(history_text)

        layout.addWidget(self.text_edit)

        button_layout = QHBoxLayout()
        copy_btn = QPushButton("Копировать")
        close_btn = QPushButton("Закрыть")

        copy_btn.clicked.connect(self.copy_text)
        close_btn.clicked.connect(self.close)

        button_layout.addWidget(copy_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

    def copy_text(self):
        pyperclip.copy(self.text_edit.toPlainText())


class ModernWindow(QMainWindow):
    def __init__(self, assistant):
        super().__init__()
        self.assistant = assistant
        self.assistant.ui_signals = UiSignals()
        self.drag_pos = QPoint()
        self.is_resizing = False
        self.is_programmatic_resize = False

        self.setWindowTitle("Voice Assistant")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.settings_expanded = False
        self.log_viewer = None
        self.history_viewer = None

        self._create_widgets()
        self._create_layout()
        self._apply_styles()
        self._connect_signals()

        self.assistant.post_ui_init()

        self.apply_ui_settings()

        # ИСПРАВЛЕНО: Правильный порядок инициализации
        self.position_window()
        self.show()
        QApplication.processEvents()

        QTimer.singleShot(200, self._create_tray_icon)

        # Обновление статуса VPN после автозапуска
        if (
            hasattr(self.assistant, "vless_manager")
            and self.assistant.vless_manager.is_running
        ):
            QTimer.singleShot(500, self.update_vpn_status)

        if self.assistant.settings.get("start_minimized"):
            QTimer.singleShot(800, self.hide)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if hasattr(self, "size_grip"):
                grip_rect = self.size_grip.geometry()
                if grip_rect.contains(event.position().toPoint()):
                    self.is_resizing = True
                    return

            self.drag_pos = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()

    def mouseMoveEvent(self, event: QMouseEvent):
        if event.buttons() == Qt.MouseButton.LeftButton and not self.is_resizing:
            self.move(event.globalPosition().toPoint() - self.drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event: QMouseEvent):
        self.is_resizing = False
        super().mouseReleaseEvent(event)

    def moveEvent(self, event):
        """Сохраняем позицию окна при перемещении"""
        super().moveEvent(event)

        # Сохраняем только если окно видимо и не в процессе инициализации
        if self.isVisible() and not self.isMinimized() and hasattr(self, "assistant"):
            pos = self.pos()
            self.assistant.save_setting("window_pos_x", pos.x())
            self.assistant.save_setting("window_pos_y", pos.y())

    def resizeEvent(self, event):
        super().resizeEvent(event)

        if hasattr(self, "size_grip"):
            grip_size = self.size_grip.sizeHint()
            self.size_grip.move(
                self.width() - grip_size.width(), self.height() - grip_size.height()
            )

        if (
            not self.is_programmatic_resize
            and not self.isMaximized()
            and not self.isMinimized()
            and self.isVisible()
        ):
            if self.settings_expanded:
                self.assistant.save_setting("expanded_width", self.width())
                self.assistant.save_setting("expanded_height", self.height())
                if hasattr(self, "expanded_width_spin"):
                    self.expanded_width_spin.blockSignals(True)
                    self.expanded_width_spin.setValue(self.width())
                    self.expanded_width_spin.blockSignals(False)
                if hasattr(self, "expanded_height_spin"):
                    self.expanded_height_spin.blockSignals(True)
                    self.expanded_height_spin.setValue(self.height())
                    self.expanded_height_spin.blockSignals(False)
            else:
                self.assistant.save_setting("compact_width", self.width())
                self.assistant.save_setting("compact_height", self.height())
                if hasattr(self, "compact_width_spin"):
                    self.compact_width_spin.blockSignals(True)
                    self.compact_width_spin.setValue(self.width())
                    self.compact_width_spin.blockSignals(False)
                if hasattr(self, "compact_height_spin"):
                    self.compact_height_spin.blockSignals(True)
                    self.compact_height_spin.setValue(self.height())
                    self.compact_height_spin.blockSignals(False)

    def _create_widgets(self):
        self.central_widget = QFrame()
        self.central_widget.setObjectName("centralWidget")
        self.setCentralWidget(self.central_widget)

        self.title_label = QLabel("Voice Assistant")
        self.title_label.setObjectName("titleLabel")
        self.status_label = QLabel("Готов к работе")
        self.status_label.setObjectName("statusLabel")

        self.bottom_bar = QFrame()
        self.bottom_bar.setObjectName("bottomBar")

        self.work_indicator = QProgressBar()
        self.work_indicator.setRange(0, 0)
        self.work_indicator.setTextVisible(False)
        self.work_indicator.setFixedHeight(8)
        self.work_indicator.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )
        self.work_indicator.setVisible(False)

        self.volume_indicator = QProgressBar()
        self.volume_indicator.setRange(0, 100)
        self.volume_indicator.setValue(0)
        self.volume_indicator.setTextVisible(False)
        self.volume_indicator.setFixedHeight(8)
        self.volume_indicator.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        self.toggle_settings_button = QPushButton("▼")
        self.toggle_settings_button.setObjectName("toggleButton")
        self.toggle_settings_button.setFixedSize(24, 24)
        self.toggle_settings_button.setFlat(True)

        self.hide_to_tray_button = QPushButton("▶")
        self.hide_to_tray_button.setObjectName("hideButton")
        self.hide_to_tray_button.setFixedSize(24, 24)
        self.hide_to_tray_button.setToolTip("Скрыть в трей")
        self.hide_to_tray_button.setFlat(True)

        self.size_grip = QSizeGrip(self.central_widget)
        self.size_grip.setFixedSize(16, 16)

        self.settings_panel = QFrame()
        self.settings_panel.setObjectName("settingsPanel")
        self.settings_panel.setVisible(False)

        settings_layout = QVBoxLayout(self.settings_panel)
        self.tabs = QTabWidget()
        settings_layout.addWidget(self.tabs)

        self.create_main_tab()
        self.create_audio_tab()
        self.create_ui_tab()
        self.create_history_tab()
        self.create_logs_tab()
        self.create_system_tab()
        # VPN вкладка
        vpn_tab = self.create_vpn_tab()
        self.tabs.addTab(vpn_tab, "VPN")
        # Обновление статуса VPN после автозапуска
        if (
            hasattr(self.assistant, "vless_manager")
            and self.assistant.vless_manager.is_running
        ):
            QTimer.singleShot(500, self.update_vpn_status)

        self.create_gemini_tab()

    def create_gemini_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # ====== НОВОЕ: API ключ Gemini ======
        api_group = QGroupBox("API ключ")
        api_layout = QVBoxLayout(api_group)

        api_layout.addWidget(QLabel("Gemini API Key:"))
        self.gemini_api_key_edit = QLineEdit()
        self.gemini_api_key_edit.setText(
            self.assistant.settings.get("gemini_api_key", "")
        )
        self.gemini_api_key_edit.setPlaceholderText("AIzaSy...")
        self.gemini_api_key_edit.setEchoMode(
            QLineEdit.EchoMode.Password
        )  # Скрывает ключ
        api_layout.addWidget(self.gemini_api_key_edit)

        # Кнопка показать/скрыть
        show_key_layout = QHBoxLayout()
        self.show_api_key_check = QCheckBox("Показать ключ")
        self.show_api_key_check.stateChanged.connect(self.toggle_api_key_visibility)
        show_key_layout.addWidget(self.show_api_key_check)
        show_key_layout.addStretch()
        api_layout.addLayout(show_key_layout)

        layout.addWidget(api_group)
        # ====================================

        # Подключаем сигнал
        self.gemini_api_key_edit.editingFinished.connect(self.on_gemini_api_key_changed)

        main_layout = layout
        self.gemini_splitter = QSplitter(Qt.Orientation.Vertical)

        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.setContentsMargins(0, 0, 0, 0)

        info_label = QLabel(
            "Здесь можно указать инструкцию для Gemini по обработке текста."
        )
        info_label.setWordWrap(True)
        top_layout.addWidget(info_label)
        top_layout.addStretch()

        bottom_widget = QGroupBox("Промпт для форматирования")
        bottom_layout = QVBoxLayout(bottom_widget)
        bottom_layout.setContentsMargins(5, 5, 5, 5)

        self.gemini_prompt_edit = QTextEdit()
        self.gemini_prompt_edit.setAcceptRichText(False)
        self.gemini_prompt_edit.setPlainText(
            self.assistant.settings.get("gemini_prompt")
        )
        bottom_layout.addWidget(self.gemini_prompt_edit)

        self.gemini_splitter.addWidget(top_widget)
        self.gemini_splitter.addWidget(bottom_widget)

        prompt_height = self.assistant.settings.get("gemini_prompt_height", 250)
        total_height = self.gemini_splitter.sizeHint().height()
        self.gemini_splitter.setSizes([total_height - prompt_height, prompt_height])

        main_layout.addWidget(self.gemini_splitter)

        activation_group = QGroupBox("Активационные слова")
        activation_layout = QVBoxLayout(activation_group)

        selection_layout = QHBoxLayout()
        selection_layout.addWidget(QLabel("Для выделения:"))
        self.selection_word_edit = QLineEdit()
        self.selection_word_edit.setText(
            self.assistant.settings.get("selection_word", "выделение")
        )
        selection_layout.addWidget(self.selection_word_edit)
        activation_layout.addLayout(selection_layout)

        pro_layout = QHBoxLayout()
        pro_layout.addWidget(QLabel("Для Pro модели:"))
        self.pro_word_edit = QLineEdit()
        self.pro_word_edit.setText(self.assistant.settings.get("pro_word", "про"))
        pro_layout.addWidget(self.pro_word_edit)
        activation_layout.addLayout(pro_layout)

        flash_layout = QHBoxLayout()
        flash_layout.addWidget(QLabel("Для Flash модели:"))
        self.flash_word_edit = QLineEdit()
        self.flash_word_edit.setText(self.assistant.settings.get("flash_word", "флеш"))
        flash_layout.addWidget(self.flash_word_edit)
        activation_layout.addLayout(flash_layout)

        main_layout.addWidget(activation_group)

        self.tabs.addTab(tab, "Gemini")

    def create_main_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        whisper_group = QGroupBox("Whisper")
        whisper_layout = QHBoxLayout(whisper_group)
        self.whisper_combo = QComboBox()
        # ИЗМЕНЕНО: только small и medium
        self.whisper_combo.addItems(["small", "medium"])
        self.whisper_combo.setCurrentText(self.assistant.settings.get("whisper_model"))
        self.whisper_combo.setMinimumContentsLength(10)

        # УДАЛЕНО: self.download_model_btn = QPushButton("Загрузить")

        whisper_layout.addWidget(self.whisper_combo)
        # УДАЛЕНО: whisper_layout.addWidget(self.download_model_btn)
        layout.addWidget(whisper_group)

        gemini_group = QGroupBox("Gemini")
        gemini_layout = QVBoxLayout(gemini_group)
        self.thinking_check = QCheckBox("Режим Thinking")
        self.thinking_check.setChecked(self.assistant.settings.get("thinking_enabled"))
        gemini_layout.addWidget(self.thinking_check)
        layout.addWidget(gemini_group)

        proxy_group = QGroupBox("Прокси")
        proxy_layout = QVBoxLayout(proxy_group)
        self.proxy_check = QCheckBox("Использовать прокси")
        self.proxy_check.setChecked(self.assistant.settings.get("proxy_enabled"))
        proxy_layout.addWidget(self.proxy_check)

        proxy_addr_layout = QHBoxLayout()
        proxy_addr_layout.addWidget(QLabel("Адрес:"))
        self.proxy_addr_edit = QLineEdit()
        self.proxy_addr_edit.setText(self.assistant.settings.get("proxy_address"))
        proxy_addr_layout.addWidget(self.proxy_addr_edit)
        proxy_layout.addLayout(proxy_addr_layout)

        proxy_port_layout = QHBoxLayout()
        proxy_port_layout.addWidget(QLabel("Порт:"))
        self.proxy_port_edit = QLineEdit()
        self.proxy_port_edit.setText(str(self.assistant.settings.get("proxy_port")))
        proxy_port_layout.addWidget(self.proxy_port_edit)
        proxy_layout.addLayout(proxy_port_layout)
        layout.addWidget(proxy_group)

        hotkey_group = QGroupBox("Режимы горячих клавиш")
        hotkey_layout = QHBoxLayout(hotkey_group)

        win_shift_group = QGroupBox("Win+Shift")
        win_shift_layout = QVBoxLayout(win_shift_group)
        self.win_shift_normal = QRadioButton("Обычный")
        self.win_shift_continuous = QRadioButton("Непрерывный")
        self.win_shift_normal.setChecked(
            self.assistant.settings.get("win_shift_mode") == "Обычный"
        )
        self.win_shift_continuous.setChecked(
            self.assistant.settings.get("win_shift_mode") == "Непрерывный"
        )
        win_shift_layout.addWidget(self.win_shift_normal)
        win_shift_layout.addWidget(self.win_shift_continuous)
        hotkey_layout.addWidget(win_shift_group)

        f1_group = QGroupBox("F1")
        f1_layout = QVBoxLayout(f1_group)
        self.f1_normal = QRadioButton("Обычный")
        self.f1_continuous = QRadioButton("Непрерывный")
        self.f1_normal.setChecked(self.assistant.settings.get("f1_mode") == "Обычный")
        self.f1_continuous.setChecked(
            self.assistant.settings.get("f1_mode") == "Непрерывный"
        )
        f1_layout.addWidget(self.f1_normal)
        f1_layout.addWidget(self.f1_continuous)
        hotkey_layout.addWidget(f1_group)
        layout.addWidget(hotkey_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Основные")

    def create_audio_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        mic_group = QGroupBox("Микрофон")
        mic_layout = QVBoxLayout(mic_group)
        mic_controls_layout = QHBoxLayout()

        self.mic_combo = QComboBox()
        self.mic_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.mic_combo.setMinimumWidth(500)
        self.mic_combo.setMaxVisibleItems(10)

        # Применяем кастомный делегат для показа полного текста
        self.mic_combo.setItemDelegate(NoElidingDelegate(self.mic_combo))

        # Заполнение списка
        self.mic_combo.addItem("По умолчанию (системный)", None)
        for i, name in get_microphone_list():
            self.mic_combo.addItem(name, i)
            index = self.mic_combo.count() - 1
            self.mic_combo.setItemData(index, name, Qt.ItemDataRole.ToolTipRole)

        # Настройка view для показа полного текста
        view = self.mic_combo.view()
        view.setTextElideMode(Qt.TextElideMode.ElideRight)
        view.setResizeMode(view.ResizeMode.Adjust)

        # Принудительное обновление размеров
        self.mic_combo.updateGeometry()
        view.updateGeometry()

        # Восстановление выбранного
        saved_index = self.assistant.settings.get("microphone_index")
        if saved_index is None:
            self.mic_combo.setCurrentIndex(0)
        else:
            combo_index = self.mic_combo.findData(saved_index)
            if combo_index != -1:
                self.mic_combo.setCurrentIndex(combo_index)
            else:
                self.mic_combo.setCurrentIndex(0)

        mic_controls_layout.addWidget(self.mic_combo, 1)

        self.refresh_mic_btn = QPushButton("🔄")
        self.refresh_mic_btn.setFixedWidth(40)
        self.refresh_mic_btn.setToolTip("Обновить список")
        mic_controls_layout.addWidget(self.refresh_mic_btn)
        self.refresh_mic_btn.clicked.connect(self.refresh_microphone_list)

        mic_layout.addLayout(mic_controls_layout)
        layout.addWidget(mic_group)

        sound_group = QGroupBox("Звуковая схема")
        sound_layout = QHBoxLayout(sound_group)
        self.sound_combo = QComboBox()
        self.sound_combo.addItems(["Стандартные", "Тихие", "Мелодичные", "Отключены"])
        self.sound_combo.setCurrentText(self.assistant.settings.get("sound_scheme"))
        sound_layout.addWidget(self.sound_combo)
        layout.addWidget(sound_group)

        quality_group = QGroupBox("Качество записи")
        quality_layout = QVBoxLayout(quality_group)
        self.quality_check = QCheckBox("Предупреждать о тихой записи")
        self.quality_check.setChecked(
            self.assistant.settings.get("audio_quality_check")
        )
        quality_layout.addWidget(self.quality_check)

        min_level_layout = QHBoxLayout()
        min_level_layout.addWidget(QLabel("Мин. уровень:"))
        self.min_level_spin = QSpinBox()
        self.min_level_spin.setRange(100, 5000)
        self.min_level_spin.setValue(self.assistant.settings.get("min_audio_level"))
        min_level_layout.addWidget(self.min_level_spin)
        quality_layout.addLayout(min_level_layout)
        layout.addWidget(quality_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Аудио")

    def create_ui_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        compact_group = QGroupBox("Компактный режим")
        compact_layout = QVBoxLayout(compact_group)

        compact_width_layout = QHBoxLayout()
        compact_width_layout.addWidget(QLabel("Ширина:"))
        self.compact_width_spin = QSpinBox()
        self.compact_width_spin.setRange(250, 1000)
        self.compact_width_spin.setValue(self.assistant.settings.get("compact_width"))
        compact_width_layout.addWidget(self.compact_width_spin)
        compact_layout.addLayout(compact_width_layout)

        compact_height_layout = QHBoxLayout()
        compact_height_layout.addWidget(QLabel("Высота:"))
        self.compact_height_spin = QSpinBox()
        self.compact_height_spin.setRange(100, 300)
        self.compact_height_spin.setValue(self.assistant.settings.get("compact_height"))
        compact_height_layout.addWidget(self.compact_height_spin)
        compact_layout.addLayout(compact_height_layout)
        layout.addWidget(compact_group)

        expanded_group = QGroupBox("Развернутый режим")
        expanded_layout = QVBoxLayout(expanded_group)

        expanded_width_layout = QHBoxLayout()
        expanded_width_layout.addWidget(QLabel("Ширина:"))
        self.expanded_width_spin = QSpinBox()
        self.expanded_width_spin.setRange(250, 1000)
        self.expanded_width_spin.setValue(self.assistant.settings.get("expanded_width"))
        expanded_width_layout.addWidget(self.expanded_width_spin)
        expanded_layout.addLayout(expanded_width_layout)

        expanded_height_layout = QHBoxLayout()
        expanded_height_layout.addWidget(QLabel("Высота:"))
        self.expanded_height_spin = QSpinBox()
        self.expanded_height_spin.setRange(300, 1200)
        self.expanded_height_spin.setValue(
            self.assistant.settings.get("expanded_height")
        )
        expanded_height_layout.addWidget(self.expanded_height_spin)
        expanded_layout.addLayout(expanded_height_layout)
        layout.addWidget(expanded_group)

        font_group = QGroupBox("Размеры шрифтов")
        font_layout = QVBoxLayout(font_group)

        title_layout = QHBoxLayout()
        title_layout.addWidget(QLabel("Заголовок:"))
        self.title_font_spin = QSpinBox()
        self.title_font_spin.setRange(10, 30)
        self.title_font_spin.setValue(self.assistant.settings.get("title_font_size"))
        title_layout.addWidget(self.title_font_spin)
        font_layout.addLayout(title_layout)

        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("Статус:"))
        self.status_font_spin = QSpinBox()
        self.status_font_spin.setRange(8, 24)
        self.status_font_spin.setValue(self.assistant.settings.get("status_font_size"))
        status_layout.addWidget(self.status_font_spin)
        font_layout.addLayout(status_layout)
        layout.addWidget(font_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Интерфейс")

    def create_history_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        size_group = QGroupBox("Окно истории")
        size_layout = QVBoxLayout(size_group)
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Ширина:"))
        self.history_width_spin = QSpinBox()
        self.history_width_spin.setRange(300, 1200)
        self.history_width_spin.setValue(
            self.assistant.settings.get("history_window_width")
        )
        width_layout.addWidget(self.history_width_spin)
        size_layout.addLayout(width_layout)
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Высота:"))
        self.history_height_spin = QSpinBox()
        self.history_height_spin.setRange(200, 1000)
        self.history_height_spin.setValue(
            self.assistant.settings.get("history_window_height")
        )
        height_layout.addWidget(self.history_height_spin)
        size_layout.addLayout(height_layout)

        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Размер шрифта:"))
        self.history_font_spin = QSpinBox()
        self.history_font_spin.setRange(6, 20)
        self.history_font_spin.setValue(
            self.assistant.settings.get("history_font_size", 10)
        )
        font_layout.addWidget(self.history_font_spin)
        size_layout.addLayout(font_layout)

        layout.addWidget(size_group)

        history_group = QGroupBox("История записей")
        history_layout = QVBoxLayout(history_group)
        self.history_combo = QComboBox()
        history_layout.addWidget(self.history_combo)

        history_buttons_layout = QHBoxLayout()
        self.view_history_btn = QPushButton("Открыть запись")
        self.clear_history_btn = QPushButton("Очистить историю")
        self.clear_history_btn.setObjectName("warningButton")
        history_buttons_layout.addWidget(self.view_history_btn)
        history_buttons_layout.addWidget(self.clear_history_btn)
        history_layout.addLayout(history_buttons_layout)
        layout.addWidget(history_group)

        self.update_history_combo()

        layout.addStretch()
        self.tabs.addTab(tab, "История")

    def create_logs_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        size_group = QGroupBox("Окно логов")
        size_layout = QVBoxLayout(size_group)
        width_layout = QHBoxLayout()
        width_layout.addWidget(QLabel("Ширина:"))
        self.log_width_spin = QSpinBox()
        self.log_width_spin.setRange(300, 1200)
        self.log_width_spin.setValue(self.assistant.settings.get("log_window_width"))
        width_layout.addWidget(self.log_width_spin)
        size_layout.addLayout(width_layout)
        height_layout = QHBoxLayout()
        height_layout.addWidget(QLabel("Высота:"))
        self.log_height_spin = QSpinBox()
        self.log_height_spin.setRange(200, 1000)
        self.log_height_spin.setValue(self.assistant.settings.get("log_window_height"))
        height_layout.addWidget(self.log_height_spin)
        size_layout.addLayout(height_layout)
        font_layout = QHBoxLayout()
        font_layout.addWidget(QLabel("Размер шрифта:"))
        self.log_font_spin = QSpinBox()
        self.log_font_spin.setRange(6, 20)
        self.log_font_spin.setValue(self.assistant.settings.get("log_font_size"))
        font_layout.addWidget(self.log_font_spin)
        size_layout.addLayout(font_layout)
        layout.addWidget(size_group)

        logs_group = QGroupBox("Управление логами")
        logs_layout = QHBoxLayout(logs_group)
        self.view_logs_btn = QPushButton("Открыть логи")
        self.clear_logs_btn = QPushButton("Очистить логи")
        self.clear_logs_btn.setObjectName("warningButton")
        logs_layout.addWidget(self.view_logs_btn)
        logs_layout.addWidget(self.clear_logs_btn)
        layout.addWidget(logs_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Логи")

    def create_system_tab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)

        autostart_group = QGroupBox("Автозагрузка")
        autostart_layout = QVBoxLayout(autostart_group)
        self.autostart_check = QCheckBox("Запускать вместе с Windows")
        self.autostart_check.setChecked(
            self.assistant.settings.get("autostart_enabled")
        )
        self.start_minimized_check = QCheckBox("Запускать свернутым в трей")
        self.start_minimized_check.setChecked(
            self.assistant.settings.get("start_minimized")
        )
        autostart_layout.addWidget(self.autostart_check)
        autostart_layout.addWidget(self.start_minimized_check)
        layout.addWidget(autostart_group)

        layout.addStretch()
        self.tabs.addTab(tab, "Система")

    def create_vpn_tab(self):
        """Создание вкладки VPN настроек"""
        tab = QWidget()
        layout = QVBoxLayout(tab)

        # Включение VLESS
        vless_group = QGroupBox("VLESS VPN")
        vless_layout = QVBoxLayout(vless_group)

        self.vless_enabled_check = QCheckBox("Использовать VLESS VPN")
        self.vless_enabled_check.setChecked(
            self.assistant.settings.get("vless_enabled", False)
        )
        vless_layout.addWidget(self.vless_enabled_check)

        # VLESS URL
        vless_layout.addWidget(QLabel("VLESS URL:"))
        self.vless_url_edit = QLineEdit()
        self.vless_url_edit.setText(self.assistant.settings.get("vless_url", ""))
        self.vless_url_edit.setPlaceholderText("vless://uuid@server:port?...")
        vless_layout.addWidget(self.vless_url_edit)

        # ====== НОВОЕ: Порт SOCKS5 ======
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("Порт SOCKS5:"))
        self.vless_port_spin = QSpinBox()
        self.vless_port_spin.setRange(1024, 65535)
        self.vless_port_spin.setValue(self.assistant.settings.get("vless_port", 10808))
        port_layout.addWidget(self.vless_port_spin)
        vless_layout.addLayout(port_layout)
        # ==============================

        # Автозапуск
        self.vless_autostart_check = QCheckBox("Автоматически подключаться при запуске")
        self.vless_autostart_check.setChecked(
            self.assistant.settings.get("vless_autostart", False)
        )
        vless_layout.addWidget(self.vless_autostart_check)

        layout.addWidget(vless_group)

        # Кнопки управления
        control_group = QGroupBox("Управление")
        control_layout = QHBoxLayout(control_group)

        self.vless_connect_btn = QPushButton("Подключить")
        self.vless_disconnect_btn = QPushButton("Отключить")
        self.vless_test_btn = QPushButton("Тест")

        self.vless_connect_btn.clicked.connect(self.vless_connect)
        self.vless_disconnect_btn.clicked.connect(self.vless_disconnect)
        self.vless_test_btn.clicked.connect(self.vless_test)

        control_layout.addWidget(self.vless_connect_btn)
        control_layout.addWidget(self.vless_disconnect_btn)
        control_layout.addWidget(self.vless_test_btn)

        layout.addWidget(control_group)

        # Статус
        self.vless_status_label = QLabel("Статус: не подключено")
        layout.addWidget(self.vless_status_label)

        layout.addStretch()

        # Подключаем сигналы для сохранения настроек
        self.vless_enabled_check.stateChanged.connect(self.on_vless_enabled_changed)
        self.vless_url_edit.editingFinished.connect(self.on_vless_url_changed)
        self.vless_port_spin.valueChanged.connect(self.on_vless_port_changed)  # НОВОЕ
        self.vless_autostart_check.stateChanged.connect(self.on_vless_autostart_changed)

        return tab

    def vless_connect(self):
        url = self.vless_url_edit.text().strip()
        if not url:
            QMessageBox.warning(self, "Ошибка", "Введите VLESS URL")
            return

        if self.assistant.vless_manager.start(url):
            self.update_vpn_status()
            self.assistant.show_status("VLESS VPN подключен!", COLORS["accent"], False)
        else:
            self.vless_status_label.setText("Статус: ✗ ошибка")
            self.assistant.show_status(
                "Ошибка подключения VPN", COLORS["btn_warning"], False
            )

    def vless_disconnect(self):
        self.assistant.vless_manager.stop()
        self.update_vpn_status()
        self.assistant.show_status("VPN отключен", COLORS["accent"], False)

    def vless_test(self):
        if self.assistant.vless_manager.is_running:
            QMessageBox.information(
                self, "VPN активен", "VLESS VPN работает\nПрокси: 127.0.0.1:10808"
            )
        else:
            QMessageBox.warning(self, "VPN неактивен", "VLESS VPN не подключен")

    def on_vless_enabled_changed(self, state):
        enabled = bool(state)
        self.assistant.save_setting("vless_enabled", enabled)
        status = "включён" if enabled else "выключен"
        self.assistant.show_status(f"VLESS VPN {status}", COLORS["accent"], False)

    def on_vless_url_changed(self):
        self.assistant.save_setting("vless_url", self.vless_url_edit.text())
        self.assistant.show_status("VLESS URL сохранён", COLORS["accent"], False)

    def on_vless_autostart_changed(self, state):
        enabled = bool(state)
        self.assistant.save_setting("vless_autostart", enabled)
        status = "включён" if enabled else "выключен"
        self.assistant.show_status(f"Автозапуск VPN {status}", COLORS["accent"], False)

    def on_vless_port_changed(self, value):
        """Обработчик изменения порта VLESS"""
        self.assistant.save_setting("vless_port", value)
        self.assistant.show_status(f"Порт VLESS VPN: {value}", COLORS["accent"], False)
        log_message(f"Порт VLESS VPN изменён на: {value}")

    def update_vpn_status(self):
        """Обновление статуса VPN в интерфейсе"""
        if not hasattr(self, "vless_status_label"):
            return

        if self.assistant.vless_manager.is_running:
            # Дополнительная проверка доступности порта
            if self.assistant.vless_manager._check_socks_port():
                self.vless_status_label.setText("Статус: ✓ подключено")
                self.vless_status_label.setStyleSheet(
                    "color: #3AE2CE; font-weight: bold;"
                )
            else:
                self.vless_status_label.setText(
                    "Статус: ⚠ процесс запущен, порт недоступен"
                )
                self.vless_status_label.setStyleSheet("color: #BF8255;")
        else:
            self.vless_status_label.setText("Статус: не подключено")
            self.vless_status_label.setStyleSheet("color: #626C71;")

    def _create_layout(self):
        self.main_layout = QVBoxLayout(self.central_widget)
        self.main_layout.setContentsMargins(20, 15, 20, 15)
        self.main_layout.setSpacing(10)

        top_bar_layout = QHBoxLayout()
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.setSpacing(10)

        top_bar_layout.addWidget(
            self.hide_to_tray_button, 0, Qt.AlignmentFlag.AlignLeft
        )
        top_bar_layout.addWidget(self.title_label, 1, Qt.AlignmentFlag.AlignCenter)
        top_bar_layout.addWidget(
            self.toggle_settings_button, 0, Qt.AlignmentFlag.AlignRight
        )

        self.main_layout.addLayout(top_bar_layout)
        self.main_layout.addWidget(
            self.status_label, alignment=Qt.AlignmentFlag.AlignCenter
        )

        bottom_bar_layout = QHBoxLayout(self.bottom_bar)
        bottom_bar_layout.setContentsMargins(0, 0, 0, 0)
        bottom_bar_layout.setSpacing(10)

        indicators_container = QFrame()
        indicators_layout = QVBoxLayout(indicators_container)
        indicators_layout.setSpacing(5)
        indicators_layout.setContentsMargins(0, 0, 0, 0)
        indicators_layout.addWidget(self.work_indicator)
        indicators_layout.addWidget(self.volume_indicator)

        indicators_container.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
        )

        bottom_bar_layout.addWidget(indicators_container, 1)

        self.main_layout.addWidget(self.bottom_bar)
        self.main_layout.addWidget(self.settings_panel)
        self.main_layout.addStretch()

    def _connect_signals(self):
        self.toggle_settings_button.clicked.connect(self.toggle_settings_panel)
        self.hide_to_tray_button.clicked.connect(self.hide)
        self.assistant.ui_signals.status_changed.connect(self.update_status)
        self.assistant.ui_signals.volume_changed.connect(self.update_volume)
        self.assistant.ui_signals.recording_state_changed.connect(
            self.on_recording_state_changed
        )
        self.assistant.ui_signals.history_updated.connect(self.update_history_combo)
        self.assistant.ui_signals.request_show_window.connect(self.show_window)
        self.assistant.ui_signals.request_hide_window.connect(self.hide)

        self.whisper_combo.currentTextChanged.connect(self.on_model_changed)
        self.thinking_check.stateChanged.connect(self.on_thinking_changed)
        self.proxy_check.stateChanged.connect(self.on_proxy_changed)
        self.proxy_addr_edit.editingFinished.connect(self.on_proxy_addr_changed)
        self.proxy_port_edit.editingFinished.connect(self.on_proxy_port_changed)

        self.win_shift_normal.toggled.connect(self.on_win_shift_mode_changed)
        self.win_shift_continuous.toggled.connect(self.on_win_shift_mode_changed)
        self.f1_normal.toggled.connect(self.on_f1_mode_changed)
        self.f1_continuous.toggled.connect(self.on_f1_mode_changed)

        self.mic_combo.currentIndexChanged.connect(self.on_mic_changed)
        self.sound_combo.currentTextChanged.connect(self.on_sound_scheme_changed)
        self.quality_check.stateChanged.connect(self.on_quality_check_changed)
        self.min_level_spin.valueChanged.connect(self.on_min_level_changed)

        self.autostart_check.stateChanged.connect(self.on_autostart_changed)
        self.start_minimized_check.stateChanged.connect(self.on_start_minimized_changed)

        self.compact_width_spin.valueChanged.connect(
            lambda v: self.on_size_setting_changed("compact_width", v)
        )
        self.compact_height_spin.valueChanged.connect(
            lambda v: self.on_size_setting_changed("compact_height", v)
        )
        self.expanded_width_spin.valueChanged.connect(
            lambda v: self.on_size_setting_changed("expanded_width", v)
        )
        self.expanded_height_spin.valueChanged.connect(
            lambda v: self.on_size_setting_changed("expanded_height", v)
        )

        self.title_font_spin.valueChanged.connect(self.apply_font_settings)
        self.status_font_spin.valueChanged.connect(self.apply_font_settings)

        self.history_width_spin.valueChanged.connect(
            lambda v: self.on_size_setting_changed("history_window_width", v)
        )
        self.history_height_spin.valueChanged.connect(
            lambda v: self.on_size_setting_changed("history_window_height", v)
        )
        self.history_font_spin.valueChanged.connect(
            lambda v: self.on_size_setting_changed("history_font_size", v)
        )

        self.log_width_spin.valueChanged.connect(
            lambda v: self.on_size_setting_changed("log_window_width", v)
        )
        self.log_height_spin.valueChanged.connect(
            lambda v: self.on_size_setting_changed("log_window_height", v)
        )
        self.log_font_spin.valueChanged.connect(
            lambda v: self.on_size_setting_changed("log_font_size", v)
        )

        self.view_logs_btn.clicked.connect(self.open_log_viewer)
        self.clear_logs_btn.clicked.connect(self.clear_logs)
        self.view_history_btn.clicked.connect(self.show_selected_history)
        self.clear_history_btn.clicked.connect(self.clear_history)
        self.gemini_prompt_edit.textChanged.connect(self.on_gemini_prompt_changed)
        self.gemini_splitter.splitterMoved.connect(self.on_gemini_splitter_moved)
        self.selection_word_edit.editingFinished.connect(self.on_selection_word_changed)
        self.pro_word_edit.editingFinished.connect(self.on_pro_word_changed)
        self.flash_word_edit.editingFinished.connect(self.on_flash_word_changed)

    def toggle_api_key_visibility(self, state):
        """Показать/скрыть API ключ"""
        if state:
            self.gemini_api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.gemini_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def on_gemini_api_key_changed(self):
        """Обработчик изменения API ключа"""
        api_key = self.gemini_api_key_edit.text().strip()
        self.assistant.save_setting("gemini_api_key", api_key)

        if api_key:
            self.assistant.show_status(
                "API ключ Gemini сохранён", COLORS["accent"], False
            )
            # Переинициализируем Gemini с новым ключом
            self.assistant.setup_gemini()
        else:
            self.assistant.show_status(
                "API ключ Gemini очищен", COLORS["btn_warning"], False
            )

        log_message("API ключ Gemini обновлён")

    def on_gemini_splitter_moved(self, pos, index):
        height = self.gemini_splitter.sizes()[1]
        self.assistant.save_setting("gemini_prompt_height", height)

    def on_gemini_prompt_changed(self):
        self.assistant.save_setting(
            "gemini_prompt", self.gemini_prompt_edit.toPlainText()
        )
        self.assistant.show_status("Промпт Gemini сохранен", COLORS["accent"], False)

    def on_selection_word_changed(self):
        self.assistant.save_setting("selection_word", self.selection_word_edit.text())
        self.assistant.show_status(
            "Слово для выделения сохранено", COLORS["accent"], False
        )

    def on_pro_word_changed(self):
        self.assistant.save_setting("pro_word", self.pro_word_edit.text())
        self.assistant.show_status(
            "Слово для Pro-модели сохранено", COLORS["accent"], False
        )

    def on_flash_word_changed(self):
        self.assistant.save_setting("flash_word", self.flash_word_edit.text())
        self.assistant.show_status(
            "Слово для Flash-модели сохранено", COLORS["accent"], False
        )

    def on_model_changed(self):
        model_name = self.whisper_combo.currentText()
        self.assistant.save_setting("whisper_model", model_name)

        log_message(f"Выбрана модель {model_name}, запускаем активацию...")

        # Активируем модель автоматически
        self.assistant.show_status(
            f"Активация {model_name}...", COLORS["accent"], True
        )

        # Запускаем активацию в отдельном потоке
        threading.Thread(
            target=self.assistant.setup_whisper, args=(model_name,), daemon=True
        ).start()

    def on_autostart_changed(self, state):
        enabled = bool(state)
        self.assistant.save_setting("autostart_enabled", enabled)
        self.assistant.set_autostart(enabled)
        status = "включена" if enabled else "выключена"
        self.assistant.show_status(f"Автозагрузка {status}", COLORS["accent"], False)

    def on_start_minimized_changed(self, state):
        enabled = bool(state)
        self.assistant.save_setting("start_minimized", enabled)
        status = "включен" if enabled else "выключен"
        self.assistant.show_status(
            f"Запуск свернутым {status}", COLORS["accent"], False
        )

    def on_thinking_changed(self, state):
        enabled = bool(state)
        self.assistant.save_setting("thinking_enabled", enabled)
        status = "включен" if enabled else "выключен"
        self.assistant.show_status(f"Режим Thinking {status}", COLORS["accent"], False)

    def on_proxy_changed(self, state):
        enabled = bool(state)
        self.assistant.save_setting("proxy_enabled", enabled)
        status = "включен" if enabled else "выключен"
        self.assistant.show_status(f"Прокси {status}", COLORS["accent"], False)
        self.assistant.reinitialize_gemini()

    def on_proxy_addr_changed(self):
        self.assistant.save_setting("proxy_address", self.proxy_addr_edit.text())
        self.assistant.show_status("Адрес прокси сохранен", COLORS["accent"], False)
        if self.assistant.settings.get("proxy_enabled"):
            self.assistant.reinitialize_gemini()

    def on_proxy_port_changed(self):
        self.assistant.save_setting("proxy_port", self.proxy_port_edit.text())
        self.assistant.show_status("Порт прокси сохранен", COLORS["accent"], False)
        if self.assistant.settings.get("proxy_enabled"):
            self.assistant.reinitialize_gemini()

    def on_win_shift_mode_changed(self):
        if self.win_shift_normal.isChecked():
            self.assistant.save_setting("win_shift_mode", "Обычный")
            self.assistant.show_status(
                "Win+Shift: Обычный режим", COLORS["accent"], False
            )
        else:
            self.assistant.save_setting("win_shift_mode", "Непрерывный")
            self.assistant.show_status(
                "Win+Shift: Непрерывный режим", COLORS["accent"], False
            )

    def on_f1_mode_changed(self):
        if self.f1_normal.isChecked():
            self.assistant.save_setting("f1_mode", "Обычный")
            self.assistant.show_status("F1: Обычный режим", COLORS["accent"], False)
        else:
            self.assistant.save_setting("f1_mode", "Непрерывный")
            self.assistant.show_status("F1: Непрерывный режим", COLORS["accent"], False)

    def on_mic_changed(self, index):
        selected_index = self.mic_combo.currentData()
        self.assistant.save_setting("microphone_index", selected_index)

        mic_name = self.mic_combo.currentText()
        log_message(f"Выбран микрофон: {mic_name} (индекс: {selected_index})")

        self.assistant.show_status(f"Микрофон: {mic_name}", COLORS["accent"], False)

    def on_sound_scheme_changed(self, scheme):
        self.assistant.save_setting("sound_scheme", scheme)
        self.assistant.show_status(f"Звуковая схема: {scheme}", COLORS["accent"], False)

    def on_quality_check_changed(self, state):
        enabled = bool(state)
        self.assistant.save_setting("audio_quality_check", enabled)
        status = "включено" if enabled else "выключено"
        self.assistant.show_status(
            f"Предупреждение о тишине {status}", COLORS["accent"], False
        )

    def on_min_level_changed(self, value):
        self.assistant.save_setting("min_audio_level", value)
        self.assistant.show_status(f"Мин. уровень: {value}", COLORS["accent"], False)

    def on_size_setting_changed(self, key, value):
        self.assistant.save_setting(key, value)
        self.assistant.show_status(
            f"Настройка '{key}' сохранена: {value}", COLORS["accent"], False
        )

    def apply_font_settings(self):
        self.assistant.save_setting("title_font_size", self.title_font_spin.value())
        self.assistant.save_setting("status_font_size", self.status_font_spin.value())
        self._update_label_fonts()

    def _update_label_fonts(self):
        title_size = self.assistant.settings.get("title_font_size")
        status_size = self.assistant.settings.get("status_font_size")
        self.title_label.setStyleSheet(
            f"color: {COLORS['white']}; font-size: {title_size}pt; font-weight: bold;"
        )
        self.status_label.setStyleSheet(
            f"color: {COLORS['accent']}; font-size: {status_size}pt;"
        )

    def apply_ui_settings(self):
        width = self.assistant.settings.get("compact_width")
        height = self.assistant.settings.get("compact_height")
        self.is_programmatic_resize = True
        self.resize(width, height)
        self.is_programmatic_resize = False
        self.setMinimumSize(250, 100)
        self._update_label_fonts()
        log_message("Настройки интерфейса применены.")

    def _apply_styles(self):
        pass

    def _create_tray_icon(self):
        """Создание иконки в системном трее"""
        log_message("Начало создания иконки в трее...")

        if not QSystemTrayIcon.isSystemTrayAvailable():
            log_message("ОШИБКА: Системный трей недоступен! Ждем...")
            QTimer.singleShot(1000, self._create_tray_icon)
            return

        self.tray_icon = QSystemTrayIcon(self)

        icon_path = resource_path("logo.ico")
        if os.path.exists(icon_path):
            self.default_icon = QIcon(icon_path)
            log_message(f"Иконка загружена из файла: {icon_path}")
        else:
            self.default_icon = self.create_colored_icon(COLORS["accent"])
            log_message("Иконка создана программно")

        self.record_icon = self.create_colored_icon(COLORS["record"])

        self.tray_icon.setIcon(self.default_icon)
        self.tray_icon.setToolTip("Voice Assistant")

        tray_menu = QMenu()
        show_action = QAction("Показать", self)
        show_action.triggered.connect(self.show_window)
        tray_menu.addAction(show_action)

        self.pause_action = QAction("Пауза", self)
        self.pause_action.setCheckable(True)
        self.pause_action.triggered.connect(self.toggle_pause)
        tray_menu.addAction(self.pause_action)

        quit_action = QAction("Выход", self)
        quit_action.triggered.connect(self.quit_application)
        tray_menu.addAction(quit_action)

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)

        self.tray_icon.show()
        log_message("✓ Иконка в трее установлена")

        QTimer.singleShot(500, self._check_tray_visibility)

    def _check_tray_visibility(self):
        if self.tray_icon.isVisible():
            log_message("✓ Иконка в трее подтверждена видимой")
        else:
            log_message("✗ Иконка невидима, повторная установка...")
            self.tray_icon.setIcon(self.default_icon)
            self.tray_icon.show()

    def create_colored_icon(self, color):
        """Создание цветной иконки программно"""
        pixmap = QPixmap(64, 64)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        painter.setBrush(QColor(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(8, 8, 48, 48)

        pen = painter.pen()
        pen.setColor(QColor(COLORS["white"]))
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(8, 8, 48, 48)

        painter.end()
        return QIcon(pixmap)

    def toggle_pause(self):
        self.assistant.is_paused = self.pause_action.isChecked()
        log_message(f"Пауза: {self.assistant.is_paused}")

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_window()

    def show_window(self):
        """Показываем окно БЕЗ изменения позиции если она уже сохранена"""
        self.showNormal()
        self.activateWindow()

        # Позиционируем только если позиция не сохранена
        if (
            self.assistant.settings.get("window_pos_x") is None
            or self.assistant.settings.get("window_pos_y") is None
        ):
            self.position_window()

    def quit_application(self):
        # Очистка VLESS VPN
        if hasattr(self.assistant, "vless_manager"):
            self.assistant.vless_manager.cleanup()
        log_message("Завершение работы приложения")
        self.tray_icon.hide()
        self.assistant.is_running = False
        QApplication.instance().quit()

    def closeEvent(self, event):
        event.ignore()
        self.hide()
        log_message("Окно скрыто в трей")

    def position_window(self):
        """Позиционирование окна с учетом сохраненной позиции"""
        if not self.screen():
            return

        screen_geo = self.screen().availableGeometry()

        # Пытаемся загрузить сохраненную позицию
        saved_x = self.assistant.settings.get("window_pos_x")
        saved_y = self.assistant.settings.get("window_pos_y")

        if saved_x is not None and saved_y is not None:
            # Проверяем что сохраненная позиция в пределах экрана
            if (
                screen_geo.left() <= saved_x <= screen_geo.right() - self.width()
                and screen_geo.top() <= saved_y <= screen_geo.bottom() - self.height()
            ):
                log_message(f"Восстановление позиции окна: ({saved_x}, {saved_y})")
                self.move(saved_x, saved_y)
                return

        # Если нет сохраненной позиции - центрируем
        top_margin = screen_geo.top() + int(screen_geo.height() * 0.1)
        new_x = screen_geo.left() + (screen_geo.width() - self.width()) // 2
        new_y = top_margin

        log_message(f"Новая позиция окна (по умолчанию): ({new_x}, {new_y})")
        self.move(new_x, new_y)

    def update_status(self, text, color, is_processing):
        self.status_label.setText(text)
        self.work_indicator.setVisible(is_processing)

    def update_volume(self, level):
        self.volume_indicator.setValue(level)

    def on_recording_state_changed(self, is_recording):
        self.work_indicator.setVisible(is_recording)
        if hasattr(self, "tray_icon"):
            self.tray_icon.setIcon(
                self.record_icon if is_recording else self.default_icon
            )

    def toggle_settings_panel(self):
        """Переключение между компактным и развернутым режимом"""
        self.is_programmatic_resize = True

        if self.settings_expanded:
            self.settings_panel.hide()
            self.toggle_settings_button.setText("▼")
            self.settings_expanded = False
            target_width = self.assistant.settings.get("compact_width")
            target_height = self.assistant.settings.get("compact_height")
            self.resize(target_width, target_height)
            log_message(
                f"Переход в компактный режим. Размер: {target_width}x{target_height}"
            )
        else:
            self.settings_expanded = True
            self.settings_panel.show()
            self.toggle_settings_button.setText("▲")
            target_width = self.assistant.settings.get("expanded_width")
            target_height = self.assistant.settings.get("expanded_height")

            if self.screen():
                screen_geo = self.screen().availableGeometry()
                current_geo = self.geometry()

                new_x = current_geo.x()
                new_y = current_geo.y()

                if new_x + target_width > screen_geo.right():
                    new_x = screen_geo.right() - target_width
                if new_y + target_height > screen_geo.bottom():
                    new_y = screen_geo.bottom() - target_height

                if new_x < screen_geo.left():
                    new_x = screen_geo.left()
                if new_y < screen_geo.top():
                    new_y = screen_geo.top()

                self.move(new_x, new_y)

            self.resize(target_width, target_height)
            log_message(
                f"Переход в развернутый режим. Размер: {target_width}x{target_height}"
            )

        self.is_programmatic_resize = False

    def update_history_combo(self):
        self.history_combo.clear()
        history_items = self.assistant.load_history_to_combo()
        for display_text, full_data in history_items:
            self.history_combo.addItem(display_text, full_data)

    def open_log_viewer(self):
        if self.log_viewer is None or not self.log_viewer.isVisible():
            self.log_viewer = LogViewerWindow(self)
            width = self.assistant.settings.get("log_window_width")
            height = self.assistant.settings.get("log_window_height")
            font_size = self.assistant.settings.get("log_font_size")
            self.log_viewer.resize(width, height)
            self.log_viewer.text_edit.setFont(QFont("Consolas", font_size))
        self.log_viewer.show()
        self.log_viewer.load_logs()

    def clear_logs(self):
        self.assistant.clear_log_file()
        if self.log_viewer and self.log_viewer.isVisible():
            self.log_viewer.load_logs()
        self.assistant.show_status("Логи очищены", COLORS["accent"], False)

    def show_selected_history(self):
        current_data = self.history_combo.currentData()
        if current_data:
            if self.history_viewer is None or not self.history_viewer.isVisible():
                self.history_viewer = HistoryViewerWindow(current_data, self)
                width = self.assistant.settings.get("history_window_width")
                height = self.assistant.settings.get("history_window_height")
                font_size = self.assistant.settings.get("history_font_size", 10)
                self.history_viewer.resize(width, height)
                self.history_viewer.text_edit.setFont(QFont("Consolas", font_size))
            else:
                self.history_viewer.text_edit.setPlainText(current_data)
            self.history_viewer.show()

    def clear_history(self):
        self.assistant.clear_history_file()
        self.update_history_combo()
        self.assistant.show_status("История очищена", COLORS["accent"], False)

    def refresh_microphone_list(self):
        """
        Перезапрашивает устройства и полностью обновляет содержимое комбобокса.
        ИСПРАВЛЕННАЯ ВЕРСИЯ с полной переинициализацией!
        """
        log_message("=" * 60)
        log_message("НАЧАЛО ОБНОВЛЕНИЯ СПИСКА МИКРОФОНОВ")

        # Сохраняем текущий выбор
        current_index = self.mic_combo.currentData()
        log_message(f"Текущий выбранный индекс: {current_index}")

        # КРИТИЧНО: Блокируем сигналы чтобы не вызывать on_mic_changed() во время обновления
        self.mic_combo.blockSignals(True)

        try:
            # Шаг 1: ПОЛНОСТЬЮ очищаем комбобокс
            self.mic_combo.clear()
            log_message("Комбобокс очищен")

            # Шаг 2: Принудительно обновляем список устройств
            # Переинициализируем sounddevice для обнаружения новых устройств
            import sounddevice as sd

            try:
                # Сбрасываем кэш устройств sounddevice
                sd._terminate()
                sd._initialize()
                log_message("Кэш sounddevice сброшен")
            except:
                log_message("Не удалось сбросить кэш sounddevice (не критично)")

            # Шаг 3: Получаем СВЕЖИЙ список микрофонов
            microphones = get_microphone_list()
            log_message(f"Получено устройств: {len(microphones)}")

            # Шаг 4: Добавляем "По умолчанию"
            self.mic_combo.addItem("По умолчанию (системный)", None)
            log_message("Добавлен пункт 'По умолчанию'")

            # Шаг 5: Добавляем каждый микрофон с детальным логированием
            for i, name in microphones:
                self.mic_combo.addItem(name, i)
                combo_idx = self.mic_combo.count() - 1
                # Сохраняем полное имя в tooltip
                self.mic_combo.setItemData(
                    combo_idx, f"Индекс: {i}, Имя: {name}", Qt.ItemDataRole.ToolTipRole
                )
                log_message(f"  [{combo_idx}] Добавлен: '{name}' (device_idx={i})")

            # Применяем делегат и настраиваем view
            self.mic_combo.setItemDelegate(NoElidingDelegate(self.mic_combo))
            view = self.mic_combo.view()
            view.setTextElideMode(Qt.TextElideMode.ElideRight)
            view.setResizeMode(view.ResizeMode.Adjust)
            self.mic_combo.updateGeometry()
            view.updateGeometry()

            # Шаг 6: Восстанавливаем предыдущий выбор или выбираем "По умолчанию"
            if current_index is not None:
                # Ищем индекс в новом списке
                combo_index = self.mic_combo.findData(current_index)
                if combo_index != -1:
                    self.mic_combo.setCurrentIndex(combo_index)
                    log_message(
                        f"Восстановлен выбор: индекс {current_index} (позиция {combo_index})"
                    )
                else:
                    self.mic_combo.setCurrentIndex(0)
                    log_message(
                        f"Предыдущий микрофон (индекс {current_index}) не найден - выбран 'По умолчанию'"
                    )
            else:
                self.mic_combo.setCurrentIndex(0)
                log_message("Выбран 'По умолчанию' (предыдущий выбор был None)")

        except Exception as e:
            log_message(f"ОШИБКА при обновлении списка микрофонов: {e}")
            log_message(traceback.format_exc())

        finally:
            # КРИТИЧНО: Разблокируем сигналы в любом случае
            self.mic_combo.blockSignals(False)

        # Шаг 7: Принудительное обновление виджета
        self.mic_combo.repaint()
        QApplication.processEvents()

        # Шаг 8: Показываем уведомление пользователю
        self.assistant.show_status(
            f"Список обновлен: {len(microphones)} мик.", COLORS["accent"], False
        )

        log_message(
            f"Обновление завершено. Всего в списке: {self.mic_combo.count()} элементов"
        )
        log_message("=" * 60)


# --- Класс бизнес-логики ---
class VoiceAssistant:
    def __init__(self):
        self.is_recording = False
        self.is_continuous_recording = False
        self.is_running = True
        self.is_paused = False
        self.keys_lock = threading.Lock()
        self.pressed_keys = set()
        self.ui_signals = None
        self.start_time = 0
        self.settings = self.load_settings()
        # Инициализация VLESS VPN менеджера с настраиваемым портом
        vless_port = int(self.settings.get("vless_port", 10808))
        self.vless_manager = VLESSManager(log_func=log_message, socks_port=vless_port)
        log_message(f"VLESS VPN инициализирован на порту: {vless_port}")

        # Автозапуск VLESS если включено
        if self.settings.get("vless_autostart", False):
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
        self.setup_gemini()

        # ИСПРАВЛЕНО: НЕ загружаем модель автоматически
        self.whisper = None
        self.clipboard_at_start = ""

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

    def load_settings(self):
        settings = DEFAULT_SETTINGS.copy()
        try:
            if os.path.exists(SETTINGS_FILE):
                with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                    settings.update(json.load(f))
                log_message(f"Настройки загружены из {SETTINGS_FILE}")
        except Exception as e:
            log_message(f"Ошибка загрузки настроек: {e}")
        return settings

    def save_setting(self, key, value):
        self.settings[key] = value
        try:
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)

            # Обновляем кэш, если изменилась настройка хоткея
            if key in ["win_shift_mode", "f1_mode"]:
                self._update_cached_settings()

        except Exception as e:
            log_message(f"Ошибка сохранения настройки '{key}': {e}")

    def _update_cached_settings(self):
        """Кэширует часто используемые настройки."""
        self.win_shift_mode = self.settings.get("win_shift_mode", "Обычный")
        self.f1_mode = self.settings.get("f1_mode", "Непрерывный")
        log_message(
            f"Кэшированные настройки обновлены: win_shift='{self.win_shift_mode}', f1='{self.f1_mode}'"
        )

    def setup_audio(self):
        self.audio = pyaudio.PyAudio()
        self.sample_rate = 16000
        self.chunk_size = 1024
        self.channels = 1

    def setup_gemini(self):
        # Загрузка API ключа ТОЛЬКО из настроек
        api_key = self.settings.get("gemini_api_key", "").strip()
        
        if not api_key:
            log_message("⚠ API ключ Gemini не указан")
            log_message("   Откройте настройки (вкладка Gemini) и введите API ключ")
            return
        """Инициализация Gemini клиента с поддержкой прокси"""
        
        # VLESS VPN имеет приоритет над ручным прокси
        if self.settings.get("vless_enabled", False) and self.vless_manager.is_running:
            # Используем порт из VLESS VPN
            vless_port = self.vless_manager.local_socks_port
            os.environ["HTTPS_PROXY"] = f"socks5://127.0.0.1:{vless_port}"
            log_message(f"Прокси VLESS VPN: 127.0.0.1:{vless_port}")

        elif self.settings.get("proxy_enabled", False):
            # Используем ручной прокси (v2rayN)
            proxy_address = self.settings.get("proxy_address", "127.0.0.1")
            proxy_port = self.settings.get("proxy_port", "10808")
            os.environ["HTTPS_PROXY"] = f"socks5://{proxy_address}:{proxy_port}"
            log_message(f"Прокси v2rayN: {proxy_address}:{proxy_port}")

        try:
            self.client = genai.Client(api_key=api_key)
            log_message("Gemini клиент инициализирован")
        except Exception as e:
            log_message(f"Ошибка инициализации Gemini: {e}")

    def reinitialize_gemini(self):
        """Переинициализация клиента Gemini для применения новых настроек"""
        log_message("Переинициализация клиента Gemini...")
        self.show_status("Применение настроек Gemini...", COLORS["accent"], True)
        self.setup_gemini()
        self.show_status("Настройки Gemini применены", COLORS["accent"], False)

    def setup_whisper(self, model_name=None):
        if model_name is None:
            model_name = self.settings["whisper_model"]

        self.show_status(f"Загрузка {model_name}...", COLORS["accent"], True)

        model_path = os.path.join(WHISPER_MODELS_DIR, f"faster-whisper-{model_name}")

        # Проверка наличия модели
        if not os.path.isdir(model_path):
            log_message(f"ОШИБКА: Папка модели не найдена: {model_path}")
            self.show_status(
                f"Модель {model_name} не найдена", COLORS["btn_warning"], False
            )
            return False

        try:
            log_separator()
            log_message(f"Загрузка Whisper ({model_name})...")

            self.whisper = WhisperModel(
                model_path,
                device="cpu",
                compute_type="int8",
            )

            log_message(f"Whisper {model_name} успешно загружен из {model_path}")
            log_separator()
            self.show_status(f"Модель {model_name} активна", COLORS["accent"], False)
            return True
        except Exception as e:
            log_message(f"КРИТИЧЕСКАЯ ОШИБКА загрузки Whisper: {e}")
            log_message(traceback.format_exc())
            log_separator()
            self.show_status(
                f"Ошибка загрузки {model_name}", COLORS["btn_warning"], False
            )
            return False

    def is_model_downloaded(self, model_name):
        """Проверяет наличие папки модели"""
        try:
            model_path = os.path.join(
                WHISPER_MODELS_DIR, f"faster-whisper-{model_name}"
            )

            if not os.path.isdir(model_path):
                log_message(f"Папка модели не найдена: {model_path}")
                return False

            log_message(f"Модель '{model_name}' найдена в {model_path}")
            return True

        except Exception as e:
            log_message(f"Ошибка проверки модели '{model_name}': {e}")
            return False

    def run(self):
        with keyboard.Listener(
            on_press=self.on_press, on_release=self.on_release
        ) as listener:
            while self.is_running:
                time.sleep(0.1)
            listener.stop()

    def key_to_comparable(self, key):
        if hasattr(key, "char") and key.char:
            return key.char.lower()
        return key

    def on_press(self, key):
        if self.is_paused:
            return

        if key == CONTINUOUS_HOTKEY:
            is_continuous = self.f1_mode == "Непрерывный"
            if self.is_recording or self.is_continuous_recording:
                self.stop_recording(continuous=is_continuous)
            else:
                self.start_recording(continuous=is_continuous)
            return

        with self.keys_lock:
            comparable_key = self.key_to_comparable(key)
            self.pressed_keys.add(comparable_key)

            hotkey_pressed = HOTKEY_COMBO.issubset(self.pressed_keys)
            if (
                hotkey_pressed
                and not self.is_recording
                and not self.is_continuous_recording
            ):
                is_continuous = self.win_shift_mode == "Непрерывный"
                self.start_recording(continuous=is_continuous)

    def on_release(self, key):
        if self.is_paused:
            return

        with self.keys_lock:
            comparable_key = self.key_to_comparable(key)
            is_hotkey_released = comparable_key in {
                self.key_to_comparable(k) for k in HOTKEY_COMBO
            }

            if comparable_key in self.pressed_keys:
                self.pressed_keys.discard(comparable_key)

            if is_hotkey_released and (
                self.is_recording or self.is_continuous_recording
            ):
                self.stop_recording(continuous=self.is_continuous_recording)

    def start_recording(self, continuous=False):
        if self.is_recording or self.is_continuous_recording:
            return

        if continuous:
            self.is_continuous_recording = True
            log_separator()
            log_message("Запуск НЕПРЕРЫВНОЙ диктовки")
        else:
            self.is_recording = True
            log_separator()
            log_message("Запуск ОБЫЧНОЙ диктовки")

        self.start_time = time.time()

        try:
            self.clipboard_at_start = pyperclip.paste()
            log_message(
                f"Сохранен буфер обмена ({len(self.clipboard_at_start)} симв.): {self.clipboard_at_start[:100]}..."
            )
        except Exception as e:
            self.clipboard_at_start = ""
            log_message(f"Ошибка сохранения буфера обмена: {e}")

        self.play_sound("start")
        self.show_status("Идет запись...", COLORS["btn_warning"], True)
        if self.ui_signals:
            self.ui_signals.request_show_window.emit()
            self.ui_signals.recording_state_changed.emit(True)

        threading.Thread(
            target=self._record_audio, args=(continuous,), daemon=True
        ).start()

    def stop_recording(self, continuous=False):
        if continuous:
            if not self.is_continuous_recording:
                return
            self.is_continuous_recording = False
            log_message("Остановка непрерывной диктовки")
        else:
            if not self.is_recording:
                return
            self.is_recording = False
            log_message("Остановка обычной диктовки")

        self.play_sound("stop")
        if self.ui_signals:
            self.ui_signals.recording_state_changed.emit(False)

    def _record_audio(self, continuous=False):
        # ИСПРАВЛЕНИЕ 1: Проверяем что модель Whisper загружена
        if self.whisper is None:
            log_message("ОШИБКА: Модель Whisper не загружена!")
            log_message(
                f"Выбранная модель в настройках: {self.settings.get('whisper_model')}"
            )
            self.show_status(
                "Загрузите модель в настройках!", COLORS["btn_warning"], False
            )
            self.play_sound("error")

            if continuous:
                self.is_continuous_recording = False
            else:
                self.is_recording = False

            threading.Timer(
                3.0, lambda: self.show_status("Готов к работе", COLORS["accent"], False)
            ).start()
            return

        # ДОБАВИТЬ после проверки (НОВАЯ СЕКЦИЯ):
        # Логируем информацию о активной модели
        active_model = self.settings.get("whisper_model", "unknown")
        log_message(f"Используется модель Whisper: {active_model}")
        log_message(f"Whisper объект инициализирован: {self.whisper is not None}")

        # ИСПРАВЛЕНИЕ 2: Правильная обработка микрофона "По умолчанию"
        mic_index = self.settings.get("microphone_index")

        if mic_index is None or mic_index == -1:
            try:
                default_info = self.audio.get_default_input_device_info()
                mic_index = default_info["index"]
                log_message(
                    f"Используется микрофон по умолчанию: {default_info['name']} (индекс {mic_index})"
                )
            except Exception as e:
                log_message(
                    f"Не удалось получить дефолтный микрофон: {e}. Используем None."
                )
                mic_index = None
        else:
            log_message(f"Используется выбранный микрофон: индекс {mic_index}")

        try:
            stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=mic_index,
                frames_per_buffer=self.chunk_size,
            )
        except (OSError, ValueError) as e:
            log_message(f"ОШИБКА: Микрофон недоступен: {e}")
            self.show_status("Микрофон не подключен", COLORS["btn_warning"], False)
            if continuous:
                self.is_continuous_recording = False
            else:
                self.is_recording = False
            return

        if continuous:
            self.audio_buffer.clear()

        frames = []
        max_level = 0

        while self.is_recording or self.is_continuous_recording:
            try:
                data = stream.read(self.chunk_size, exception_on_overflow=False)
                frames.append(data)
                audio_np = np.frombuffer(data, dtype=np.int16)
                level = np.abs(audio_np).mean()
                max_level = max(max_level, level)
                self.update_volume_indicator(level)

                if (
                    continuous
                    and len(frames) * self.chunk_size / self.sample_rate >= 15
                ):
                    audio_data = b"".join(frames)
                    audio_np_segment = (
                        np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
                        / 32768.0
                    )
                    threading.Thread(
                        target=self._process_continuous_segment,
                        args=(audio_np_segment,),
                        daemon=True,
                    ).start()

                    overlap_frames = int(5 * self.sample_rate / self.chunk_size)
                    frames = frames[-overlap_frames:]

            except Exception as e:
                log_message(f"Ошибка чтения аудио: {e}")
                break

        stream.stop_stream()
        stream.close()
        log_message(f"Аудио поток закрыт. Записано фреймов: {len(frames)}")

        if frames:
            if self.settings.get(
                "audio_quality_check"
            ) and max_level < self.settings.get("min_audio_level"):
                log_message(
                    f"ВНИМАНИЕ: Низкий уровень аудио: {max_level} < {self.settings.get('min_audio_level')}"
                )
                self.show_status("Слишком тихо!", COLORS["btn_warning"], False)
                self.play_sound("error")
                threading.Timer(
                    2.0,
                    lambda: self.show_status("Готов к работе", COLORS["accent"], False),
                ).start()
                return

            log_message(f"Максимальный уровень громкости: {max_level}")
            audio_data = b"".join(frames)
            audio_np = (
                np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
            )

            if continuous:
                self._process_audio_whisper(audio_np, is_final_segment=True)
            else:
                self._process_audio_whisper(audio_np, is_final_segment=False)
        else:
            log_message("ОШИБКА: Нет записанных аудио данных")
            self.show_status("Нет аудио", COLORS["btn_warning"], False)
            self.play_sound("error")
            threading.Timer(
                2.0, lambda: self.show_status("Готов к работе", COLORS["accent"], False)
            ).start()

    def _process_continuous_segment(self, audio_np):
        """Обрабатывает сегмент в непрерывном режиме, только добавляя в буфер"""
        try:
            log_message("Обработка промежуточного сегмента...")
            segments, _ = self.whisper.transcribe(audio_np, language=LANGUAGE)
            text = " ".join([s.text for s in segments]).strip()
            if text:
                # Ограничение размера буфера для предотвращения утечки памяти
                MAX_BUFFER_SIZE = 100
                if len(self.audio_buffer) >= MAX_BUFFER_SIZE:
                    log_message(
                        f"ПРЕДУПРЕЖДЕНИЕ: Буфер непрерывной записи достиг предела ({MAX_BUFFER_SIZE}). Старый сегмент удален."
                    )
                    self.audio_buffer.pop(0)

                self.audio_buffer.append(text)
                log_message(
                    f"Добавлен сегмент в буфер ({len(text)} симв.): {text[:100]}..."
                )
        except Exception as e:
            log_message(f"Ошибка обработки сегмента: {e}\n{traceback.format_exc()}")

    def _process_audio_whisper(self, audio_np, is_final_segment=False):
        """Финальная обработка аудио, распознавание и вызов _handle_final_text"""
        self.show_status("Обработка...", COLORS["accent"], True)
        try:
            model_name = self.settings.get("whisper_model", "unknown")
            model_path = os.path.join(
                WHISPER_MODELS_DIR, f"faster-whisper-{model_name}"
            )

            log_message(f"==================== WHISPER ОБРАБОТКА ====================")
            log_message(f"Выбранная модель: {model_name}")
            log_message(f"Путь к модели: {model_path}")
            log_message(f"Модель активна: {self.whisper is not None}")
            log_message(f"Начало распознавания...")
            whisper_start = time.time()

            segments, _ = self.whisper.transcribe(audio_np, language=LANGUAGE)
            text = " ".join([s.text for s in segments]).strip()

            whisper_time = time.time() - whisper_start
            log_message(
                f"Распознавание завершено за {whisper_time:.2f}с (модель: {model_name})"
            )
            log_message(f"==========================================================")

            if text:
                log_message(f"Распознанный текст ({len(text)} символов): {text}")

                words = [
                    re.sub(r"[^\w\s]", "", w).lower() for w in text.strip().split()
                ]
                use_pro_model = False
                use_flash_model = False
                use_selected_text = False
                words_to_skip = 0

                pro_word = self.settings.get("pro_word", "про")
                flash_word = self.settings.get("flash_word", "флеш")
                selection_word = self.settings.get("selection_word", "выделение")

                if len(words) > 0:
                    if words[0] == selection_word:
                        use_selected_text = True
                        if len(words) > 1:
                            if words[1] == pro_word:
                                use_pro_model = True
                                words_to_skip = 2
                                log_message("Активирован режим 'Выделение Pro'")
                            elif words[1] == flash_word:
                                use_flash_model = True
                                words_to_skip = 2
                                log_message("Активирован режим 'Выделение Flash'")
                        if words_to_skip == 0:  # Если просто "Выделение"
                            use_pro_model = True  # По умолчанию Pro
                            words_to_skip = 1
                            log_message(
                                "Активирован режим 'Выделение' (по умолчанию Pro)"
                            )
                    elif words[0] == pro_word:
                        use_pro_model = True
                        words_to_skip = 1
                        log_message("Активирован режим Gemini Pro")
                    elif words[0] == flash_word:
                        use_flash_model = True
                        words_to_skip = 1
                        log_message("Активирован режим Gemini Flash")

                if words_to_skip > 0:
                    text = " ".join(text.strip().split()[words_to_skip:])

                if is_final_segment:
                    self.audio_buffer.append(text)
                    full_text = " ".join(self.audio_buffer)
                    log_message(
                        f"Собран полный текст из {len(self.audio_buffer)} сегментов для Gemini ({len(full_text)} симв.)"
                    )
                    self._handle_final_text(
                        full_text,
                        insert_text=True,
                        use_pro=use_pro_model,
                        use_flash=use_flash_model,
                        use_selection=use_selected_text,
                    )
                else:
                    self._handle_final_text(
                        text,
                        insert_text=True,
                        use_pro=use_pro_model,
                        use_flash=use_flash_model,
                        use_selection=use_selected_text,
                    )
            else:
                log_message("ОШИБКА: Whisper вернул пустой результат")
                self.show_status("Не распознано", COLORS["btn_warning"], False)
                self.play_sound("error")
                threading.Timer(
                    2.0,
                    lambda: self.show_status("Готов к работе", COLORS["accent"], False),
                ).start()
        except Exception as e:
            log_message(
                f"КРИТИЧЕСКАЯ ОШИБКА обработки Whisper: {e}\n{traceback.format_exc()}"
            )
            self.show_status("Ошибка Whisper", COLORS["btn_warning"], False)
            self.play_sound("error")
            threading.Timer(
                2.0, lambda: self.show_status("Готов к работе", COLORS["accent"], False)
            ).start()

    def _handle_final_text(
        self,
        text,
        insert_text=False,
        use_pro=False,
        use_flash=False,
        use_selection=False,
    ):
        """Обработка финального текста с отправкой в Gemini"""
        if not isinstance(text, str) or not text.strip():
            log_message("ОШИБКА: Получен пустой или некорректный текст для обработки.")
            return

        # Обрезаем текст до максимальной длины и удаляем лишние пробелы
        text = text.strip()[:10000]

        final_text = text
        try:
            selected_text = ""
            if use_selection:
                selected_text = self.clipboard_at_start
                log_message(
                    f"Использован сохраненный буфер обмена ({len(selected_text)} симв.): {selected_text[:100]}..."
                )

            is_direct_command = (
                use_pro or use_flash or (use_selection and selected_text)
            )

            if use_selection and selected_text:
                prompt = f'Выделенный текст:\n"{selected_text}"\n\nЗадача: {text}'
                log_message("Промпт сформирован с выделенным текстом")
            elif is_direct_command:
                prompt = text
                log_message("Промпт сформирован как прямая команда")
            else:
                user_prompt = self.settings.get("gemini_prompt")
                prompt = f"{user_prompt} Вот текст: '{text}'"

            if use_pro:
                model_name = self.settings.get("gemini_model_pro")
            elif use_flash:
                model_name = self.settings.get("gemini_model_default")
            else:  # По умолчанию, если нет команд
                model_name = self.settings.get("gemini_model_default")

            thinking_mode = (
                "Thinking" if self.settings.get("thinking_enabled") else "Обычный"
            )
            log_message(
                f"Отправка в Gemini (модель: {model_name}, режим: {thinking_mode})"
            )

            if use_pro:
                self.show_status("Gemini Pro...", COLORS["accent"], True)
            elif use_flash:
                self.show_status("Gemini Flash...", COLORS["accent"], True)
            else:
                self.show_status("Обработка Gemini...", COLORS["accent"], True)

            # Pro модель всегда требует thinking mode
            if use_pro or self.settings.get("thinking_enabled"):
                config = types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=-1)
                )
            else:
                config = types.GenerateContentConfig(
                    thinking_config=types.ThinkingConfig(thinking_budget=0)
                )

            gemini_start = time.time()
            response = self.client.models.generate_content(
                model=model_name, contents=prompt, config=config
            )
            final_text = response.text.strip()
            gemini_time = time.time() - gemini_start
            log_message(f"Gemini обработка завершена за {gemini_time:.2f}с.")
            log_message(f"Итоговый текст: {final_text}")

        except Exception as e:
            log_message(f"ОШИБКА Gemini: {e}\n{traceback.format_exc()}")
            self.show_status("Ошибка Gemini", COLORS["btn_warning"], False)
            final_text = text

        if self.audio_buffer:
            log_message(f"Очищаем буфер (было {len(self.audio_buffer)} сегментов)")
            self.audio_buffer.clear()

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            history_logger.info(f"{timestamp}\n{final_text}\n---")
            log_message("Текст сохранен в историю")
        except Exception as e:
            log_message(f"Ошибка записи в историю: {e}")

        if self.ui_signals:
            self.ui_signals.history_updated.emit()

        if insert_text:
            pyperclip.copy(final_text)
            log_message("Текст скопирован в буфер обмена")

            ahk_exe = resource_path("paste_text.exe")
            if os.path.exists(ahk_exe):
                try:
                    subprocess.Popen(
                        [ahk_exe, final_text], creationflags=subprocess.CREATE_NO_WINDOW
                    )
                    log_message("Текст вставлен через AHK")
                except Exception as e:
                    log_message(f"Ошибка AHK: {e}")
            else:
                log_message("AHK не найден, текст только в буфере обмена")

            if self.ui_signals:
                self.ui_signals.request_hide_window.emit()

            self.show_status(
                f"Готово! ({len(final_text)} симв.)", COLORS["accent"], False
            )
            total_time = time.time() - self.start_time
            log_message(f"Общее время от нажатия до вставки: {total_time:.2f}с.")
            log_separator()
            threading.Timer(
                2.0, lambda: self.show_status("Готов к работе", COLORS["accent"], False)
            ).start()

    def show_status(self, txt, color, spinning=False):
        if self.ui_signals:
            self.ui_signals.status_changed.emit(txt, color, spinning)

    def update_volume_indicator(self, volume_level):
        if self.ui_signals:
            normalized = min(100, max(0, int((volume_level / 5000) * 100)))
            self.ui_signals.volume_changed.emit(normalized)

    def play_sound(self, sound_type):
        scheme = self.settings.get("sound_scheme")
        if scheme == "Отключены":
            return

        sounds = SOUND_SCHEMES.get(scheme, {})
        if sound_type in sounds:
            freq, duration = sounds[sound_type]
            threading.Thread(
                target=lambda: winsound.Beep(freq, duration), daemon=True
            ).start()

    def load_history_to_combo(self):
        """Загрузка истории для комбобокса"""
        items = []
        try:
            if os.path.exists(HISTORY_FILE):
                with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                    content = f.read()

                entries = re.split(r"\n---\n?", content.strip())

                for entry in reversed(entries[-10:]):
                    entry = entry.strip()
                    if not entry:
                        continue

                    lines = entry.split("\n", 1)
                    if len(lines) >= 2:
                        timestamp = lines[0].strip()
                        text = lines[1].strip()

                        display_text = text.replace("\n", " ")
                        display = f"{timestamp} — {display_text[:50]}{'...' if len(display_text) > 50 else ''}"
                        items.append((display, text))
        except Exception as e:
            log_message(f"Ошибка загрузки истории: {e}")

        return items

    def clear_log_file(self):
        """Очистка файла логов"""
        try:
            global logger
            # Безопасное закрытие и удаление обработчиков
            for handler in list(logger.handlers):
                handler.close()
                logger.removeHandler(handler)

            # Перезапись файла
            with open(LOG_FILE, "w", encoding="utf-8", errors="replace") as f:
                f.write("")

            # Переинициализация
            globals()["logger"] = setup_logging()
            log_message("Лог-файл очищен")
        except Exception as e:
            # Используем print, так как логгер может быть не в порядке
            print(f"ОШИБКА очистки логов: {e}")

    def clear_history_file(self):
        """Очистка файла истории"""
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                f.write("")
            log_message("Файл истории очищен")
            if self.ui_signals:
                self.ui_signals.history_updated.emit()
        except Exception as e:
            log_message(f"Ошибка очистки файла истории: {e}")

    def set_autostart(self, enabled):
        """Управление автозагрузкой через папку Startup"""
        try:
            startup_folder = os.path.join(
                os.environ["APPDATA"], r"Microsoft\Windows\Start Menu\Programs\Startup"
            )

            shortcut_path = os.path.join(startup_folder, "VoiceAssistant.lnk")

            if enabled:
                if getattr(sys, "frozen", False):
                    target_path = sys.executable
                else:
                    target_path = os.path.abspath(sys.argv[0])

                target_path = os.path.normpath(target_path)

                if not os.path.exists(target_path):
                    log_message(f"ОШИБКА: Файл не существует: {target_path}")
                    self.show_status(
                        "Ошибка автозагрузки", COLORS["btn_warning"], False
                    )
                    return

                vbs_script = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{shortcut_path}"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target_path}"
oLink.WorkingDirectory = "{os.path.dirname(target_path)}"
oLink.Description = "Voice Assistant"
oLink.Save
"""

                vbs_path = os.path.join(os.environ["TEMP"], "create_shortcut.vbs")

                try:
                    with open(vbs_path, "w") as f:
                        f.write(vbs_script)

                    subprocess.run(
                        ["cscript", "//Nologo", vbs_path],
                        capture_output=True,
                        creationflags=subprocess.CREATE_NO_WINDOW,
                    )

                    os.remove(vbs_path)

                    if os.path.exists(shortcut_path):
                        log_message(
                            f"Автозагрузка включена через Startup: {shortcut_path}"
                        )
                        self.show_status(
                            "Автозагрузка включена", COLORS["accent"], False
                        )
                    else:
                        log_message("ОШИБКА: Не удалось создать ярлык")
                        self.show_status(
                            "Ошибка автозагрузки", COLORS["btn_warning"], False
                        )

                except Exception as e:
                    log_message(f"ОШИБКА создания ярлыка: {e}")
                    log_message(traceback.format_exc())
            else:
                if os.path.exists(shortcut_path):
                    try:
                        os.remove(shortcut_path)
                        log_message("Автозагрузка отключена")
                        self.show_status(
                            "Автозагрузка отключена", COLORS["accent"], False
                        )
                    except Exception as e:
                        log_message(f"ОШИБКА отключения автозагрузки: {e}")
                        self.show_status(
                            "Ошибка автозагрузки", COLORS["btn_warning"], False
                        )
        except Exception as e:
            log_message(f"ОШИБКА управления автозагрузкой: {e}")
            log_message(traceback.format_exc())


# --- Точка входа ---
def main():
    try:
        with open("startup_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] Начало функции main()\n")

        log_separator()
        log_message("Voice Assistant запущен")
        log_separator()

        with open("startup_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] Создание QApplication\n")

        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        with open("startup_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] Применение стилей\n")

        # --- Глобальное применение стилей ---
        app.setStyleSheet(
            f"""
            QMenu {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['white']};
                border: 1px solid {COLORS['accent']};
            }}
            QMenu::item:selected {{
                background-color: {COLORS['accent']};
                color: {COLORS['bg_dark']};
            }}
            #centralWidget {{
                background-color: {COLORS['bg_main']};
                border-radius: 12px;
            }}
            #titleLabel {{
                color: {COLORS['white']};
                font-weight: bold;
            }}
            #statusLabel {{
                color: {COLORS['accent']};
            }}
            QProgressBar {{
                border: none;
                border-radius: 4px;
                background-color: {COLORS['bg_dark']};
            }}
            QProgressBar::chunk {{
                background-color: {COLORS['accent']};
                border-radius: 4px;
            }}
            #toggleButton, #hideButton {{
                background-color: transparent;
                color: {COLORS['accent']};
                font-size: 12pt;
                border: none;
                border-radius: 12px;
            }}
            #toggleButton:hover, #hideButton:hover {{
                background-color: {COLORS['bg_dark']};
            }}
            #settingsPanel, QTabWidget, QWidget, QGroupBox {{
                color: {COLORS['white']};
                background-color: transparent;
                border: none;
            }}
            QGroupBox {{
                border: 1px solid {COLORS['border_grey']};
                border-radius: 6px;
                margin-top: 8px;
                padding: 10px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
            }}
            QTabWidget::pane {{
                border: none;
            }}
            QTabBar::tab {{
                background: {COLORS['bg_dark']};
                color: {COLORS['white']};
                padding: 8px 12px;
                border-radius: 4px;
            }}
            QTabBar::tab:selected {{
                background: {COLORS['accent']};
                color: {COLORS['bg_dark']};
            }}
            QComboBox, QLineEdit, QPushButton, QSpinBox {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['white']};
                border: 1px solid {COLORS['accent']};
                border-radius: 4px;
                padding: 8px;
            }}
            QPushButton {{
                background-color: {COLORS['btn_standard']};
            }}
            QPushButton:hover {{
                background-color: #5F92E5;
            }}
            #warningButton {{
                background-color: {COLORS['btn_warning']};
            }}
            #warningButton:hover {{
                background-color: #d99a6c;
            }}
            QCheckBox::indicator, QRadioButton::indicator {{
                width: 16px;
                height: 16px;
                border: 1px solid {COLORS['accent']};
                border-radius: 4px;
            }}
            QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
                background-color: {COLORS['accent']};
            }}
            QTextEdit {{
                background-color: {COLORS['bg_dark']};
                color: {COLORS['white']};
                border: 1px solid {COLORS['accent']};
                border-radius: 4px;
            }}
            QSizeGrip {{
                background-color: transparent;
                image: none;
            }}
        """
        )
        # --- Конец глобальных стилей ---

        with open("startup_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] Создание VoiceAssistant\n")

        assistant = VoiceAssistant()

        with open("startup_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] Создание ModernWindow\n")

        window = ModernWindow(assistant)

        with open("startup_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] Запуск потока ассистента\n")

        assistant_thread = threading.Thread(target=assistant.run, daemon=True)
        assistant_thread.start()

        with open("startup_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] Окно создано, запуск app.exec()\n")

        # Окно уже показано в __init__ ModernWindow

        sys.exit(app.exec())

    except Exception as e:
        with open("startup_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.datetime.now()}] КРИТИЧЕСКАЯ ОШИБКА:\n")
            f.write(f"{e}\n")
            f.write(f"{traceback.format_exc()}\n")

        log_message(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        log_message(traceback.format_exc())
        log_separator()

        print(f"Критическая ошибка: {e}")
        print(traceback.format_exc())
        input("Нажмите Enter для выхода...")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()
