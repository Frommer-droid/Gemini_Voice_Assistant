# -*- coding: utf-8 -*-
import ctypes
import os
import subprocess
import threading
from ctypes import wintypes
from typing import Optional

import pyperclip
from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QStackedWidget,
    QStyledItemDelegate,
    QTextEdit,
    QVBoxLayout,
    QWidget,
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


class LogViewerWindow(QDialog):
    def __init__(self, log_file: str, parent=None):
        super().__init__(parent)
        self._log_file = log_file
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
        clear_btn = QPushButton("Очистить")
        close_btn = QPushButton("Закрыть")

        refresh_btn.clicked.connect(self.load_logs)
        copy_btn.clicked.connect(self.copy_logs)
        clear_btn.clicked.connect(self.clear_logs)
        close_btn.clicked.connect(self.close)

        button_layout.addWidget(refresh_btn)
        button_layout.addWidget(copy_btn)
        button_layout.addWidget(clear_btn)
        button_layout.addWidget(close_btn)
        layout.addLayout(button_layout)

        self.load_logs()

    def load_logs(self):
        try:
            if os.path.exists(self._log_file):
                with open(self._log_file, "r", encoding="utf-8") as f:
                    self.text_edit.setPlainText(f.read())
                    cursor = self.text_edit.textCursor()
                    cursor.movePosition(cursor.MoveOperation.End)
                    self.text_edit.setTextCursor(cursor)
        except Exception as e:
            self.text_edit.setPlainText(f"Ошибка загрузки логов: {e}")

    def copy_logs(self):
        pyperclip.copy(self.text_edit.toPlainText())

    def clear_logs(self):
        """Очищает окно и файл логов."""
        try:
            self.text_edit.clear()
            with open(self._log_file, "w", encoding="utf-8") as f:
                f.write("")
        except Exception as e:
            self.text_edit.setPlainText(f"Ошибка очистки логов: {e}")


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


class FirstRunWizard(QDialog):
    def __init__(self, assistant, parent=None, exe_dir: Optional[str] = None, log_func=None):
        super().__init__(parent)
        self.assistant = assistant
        self._exe_dir = exe_dir or os.getcwd()
        self._log = log_func or (lambda _msg: None)
        self._everything_launch_in_progress = False
        self._step_titles = [
            "Шаг 1 из 4: API ключ Gemini",
            "Шаг 2 из 4: VLESS ключ",
            "Шаг 3 из 4: Everything",
            "Шаг 4 из 4: Готово",
        ]

        self.setWindowTitle("Мастер первого запуска")
        self.setModal(True)
        self.setMinimumWidth(560)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self._build_ui()
        self._update_step_label()
        self._update_nav_buttons()
        self._refresh_everything_status()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.step_label = QLabel()
        self.step_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(self.step_label)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.stack.addWidget(self._build_api_page())
        self.stack.addWidget(self._build_vless_page())
        self.stack.addWidget(self._build_everything_page())
        self.stack.addWidget(self._build_finish_page())

        nav_layout = QHBoxLayout()
        nav_layout.addStretch()
        self.back_btn = QPushButton("Назад")
        self.next_btn = QPushButton("Далее")
        self.finish_btn = QPushButton("Готово")
        self.cancel_btn = QPushButton("Пропустить")
        nav_layout.addWidget(self.cancel_btn)
        nav_layout.addWidget(self.back_btn)
        nav_layout.addWidget(self.next_btn)
        nav_layout.addWidget(self.finish_btn)
        layout.addLayout(nav_layout)

        self.back_btn.clicked.connect(self._go_back)
        self.next_btn.clicked.connect(self._go_next)
        self.finish_btn.clicked.connect(self._finish)
        self.cancel_btn.clicked.connect(self.reject)
        self.stack.currentChanged.connect(self._on_step_changed)

    def _build_api_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        info = QLabel(
            "Введите API ключ Gemini. Он нужен для работы нейросети.\n"
            "Если ключа пока нет, оставьте поле пустым - можно заполнить позже "
            "в настройках."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("AIzaSy...")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setText(self.assistant.settings.get("gemini_api_key", ""))
        layout.addWidget(self.api_key_edit)

        self.api_key_show = QCheckBox("Показать ключ")
        self.api_key_show.stateChanged.connect(self._toggle_api_key_visibility)
        layout.addWidget(self.api_key_show)

        layout.addStretch()
        return page

    def _build_vless_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        info = QLabel(
            "Введите VLESS URL для VPN, если используете его для доступа к Gemini.\n"
            "Можно оставить пустым и настроить позже."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.vless_url_edit = QLineEdit()
        self.vless_url_edit.setPlaceholderText("vless://uuid@server:port?...")
        self.vless_url_edit.setText(self.assistant.settings.get("vless_url", ""))
        layout.addWidget(self.vless_url_edit)

        self.vless_enabled_check = QCheckBox("Использовать VLESS VPN")
        self.vless_enabled_check.setChecked(
            self.assistant.settings.get("vless_enabled", False)
        )
        layout.addWidget(self.vless_enabled_check)

        self.vless_autostart_check = QCheckBox("Автоматически подключаться при запуске")
        self.vless_autostart_check.setChecked(
            self.assistant.settings.get("vless_autostart", False)
        )
        self.vless_autostart_check.setEnabled(self.vless_enabled_check.isChecked())
        layout.addWidget(self.vless_autostart_check)

        self.vless_enabled_check.stateChanged.connect(
            self._on_vless_enabled_toggled
        )
        layout.addStretch()
        return page

    def _build_everything_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        info = QLabel(
            "Кнопки запускают сервис Everything для индексации файлов и папок.\n"
            "После завершения индексации окно можно закрыть."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        self.everything_status_label = QLabel()
        layout.addWidget(self.everything_status_label)

        self.everything_launch_btn = QPushButton("Запустить сервис")
        self.everything_launch_btn.setToolTip(
            "Запускает bat-файл и нажимает кнопки через AHK helper"
        )
        self.everything_launch_btn.clicked.connect(
            self._launch_everything_via_ahk
        )
        layout.addWidget(self.everything_launch_btn)

        layout.addStretch()
        return page

    def _build_finish_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        info = QLabel(
            "Основные настройки завершены.\n"
            "Остальные параметры можно настроить в развернутом режиме.\n"
            "Автозапуск при старте Windows и запуск в трей находятся во вкладке <Система>."
        )
        info.setWordWrap(True)
        layout.addWidget(info)
        layout.addStretch()
        return page

    def _toggle_api_key_visibility(self):
        if self.api_key_show.isChecked():
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Normal)
        else:
            self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)

    def _on_vless_enabled_toggled(self, state):
        enabled = state == Qt.CheckState.Checked.value
        self.vless_autostart_check.setEnabled(enabled)
        if not enabled:
            self.vless_autostart_check.setChecked(False)

    def _on_step_changed(self):
        self._update_step_label()
        self._update_nav_buttons()
        if self.stack.currentIndex() == 2:
            self._refresh_everything_status()

    def _update_step_label(self):
        index = self.stack.currentIndex()
        if 0 <= index < len(self._step_titles):
            self.step_label.setText(self._step_titles[index])

    def _update_nav_buttons(self):
        index = self.stack.currentIndex()
        last_index = self.stack.count() - 1
        self.back_btn.setEnabled(index > 0)
        self.next_btn.setVisible(index < last_index)
        self.finish_btn.setVisible(index == last_index)

    def _go_next(self):
        index = self.stack.currentIndex()
        if index < self.stack.count() - 1:
            self.stack.setCurrentIndex(index + 1)

    def _go_back(self):
        index = self.stack.currentIndex()
        if index > 0:
            self.stack.setCurrentIndex(index - 1)

    def _finish(self):
        self._apply_settings()
        self.assistant.save_setting("first_run_completed", True)
        self.assistant.warmup_everything_async()
        self.accept()

    def _apply_settings(self):
        prev_api = self.assistant.settings.get("gemini_api_key", "").strip()
        new_api = self.api_key_edit.text().strip()
        if new_api != prev_api:
            self.assistant.save_setting("gemini_api_key", new_api)
            if new_api:
                self.assistant.reinitialize_gemini()

        prev_vless_enabled = self.assistant.settings.get("vless_enabled", False)
        prev_vless_autostart = self.assistant.settings.get("vless_autostart", False)
        new_vless_enabled = self.vless_enabled_check.isChecked()
        new_vless_autostart = self.vless_autostart_check.isChecked()

        if new_vless_enabled != prev_vless_enabled:
            self.assistant.save_setting("vless_enabled", new_vless_enabled)
            if not new_vless_enabled and self.assistant.vless_manager.is_running:
                self.assistant.vless_manager.stop()

        if new_vless_autostart != prev_vless_autostart:
            self.assistant.save_setting("vless_autostart", new_vless_autostart)

        prev_vless = self.assistant.settings.get("vless_url", "").strip()
        new_vless = self.vless_url_edit.text().strip()
        if new_vless != prev_vless:
            self.assistant.save_setting("vless_url", new_vless)
            if new_vless:
                self._start_vless_if_needed(new_vless)
        elif new_vless:
            self._start_vless_if_needed(new_vless)

        parent = self.parent()
        if parent:
            if hasattr(parent, "gemini_api_key_edit"):
                parent.gemini_api_key_edit.setText(new_api)
            if hasattr(parent, "vless_url_edit"):
                parent.vless_url_edit.setText(new_vless)
            if hasattr(parent, "vless_enabled_check"):
                parent.vless_enabled_check.setChecked(new_vless_enabled)
            if hasattr(parent, "vless_autostart_check"):
                parent.vless_autostart_check.setChecked(new_vless_autostart)
            if hasattr(parent, "update_vpn_status"):
                QTimer.singleShot(0, parent.update_vpn_status)

    def _start_vless_if_needed(self, url: str):
        if not self.assistant.settings.get("vless_enabled", False):
            return
        if not self.assistant.settings.get("vless_autostart", False):
            return
        if self.assistant.vless_manager.is_running:
            return

        def _task():
            self._log("Запуск VLESS VPN после мастера первого запуска...")
            if self.assistant.vless_manager.start(url):
                self._log("VLESS VPN подключен после мастера первого запуска.")
                parent = self.parent()
                if parent and hasattr(parent, "update_vpn_status"):
                    QTimer.singleShot(0, parent.update_vpn_status)
            else:
                self._log("Не удалось подключить VLESS VPN после мастера первого запуска.")

        threading.Thread(target=_task, daemon=True).start()

    def _refresh_everything_status(self):
        handler = getattr(self.assistant, "search_handler", None)
        exe_path = getattr(handler, "everything_path", "") if handler else ""
        if not exe_path or not os.path.exists(exe_path):
            self.everything_status_label.setText("Everything.exe не найден.")
            return
        bat_path = os.path.join(os.path.dirname(exe_path), "install_service.bat")
        if not os.path.exists(bat_path):
            self.everything_status_label.setText(
                "install_service.bat не найден в папке Everything."
            )
            return

        is_running = False
        if handler:
            try:
                is_running = handler.is_everything_process_running()
            except Exception:
                is_running = False
        if is_running:
            self.everything_status_label.setText("Статус: Everything уже запущен.")
        else:
            self.everything_status_label.setText("Статус: готов к запуску.")

    def _launch_everything_for_indexing(self, status_label: Optional[str] = None):
        if self._everything_launch_in_progress:
            return
        handler = getattr(self.assistant, "search_handler", None)
        exe_path = getattr(handler, "everything_path", "") if handler else ""
        if not exe_path or not os.path.exists(exe_path):
            self.everything_status_label.setText("Everything.exe не найден.")
            return
        bat_path = os.path.join(os.path.dirname(exe_path), "install_service.bat")
        if not os.path.exists(bat_path):
            self.everything_status_label.setText(
                "install_service.bat не найден. Поместите его в папку Everything."
            )
            return
        was_running = False
        if handler:
            try:
                was_running = handler.is_everything_process_running()
            except Exception:
                was_running = False
        if was_running:
            self.everything_status_label.setText(
                "Everything уже запущен. Пробую повторный запуск."
            )

        self._everything_launch_in_progress = True
        self.everything_launch_btn.setEnabled(False)
        self.everything_status_label.setText(
            status_label or "Запускаю сервис Everything..."
        )

        def _task():
            ok = False
            try:
                if handler:
                    handler.block_autostart(30, "мастер первого запуска")
                self._log(f"Запуск install_service.bat через проводник: {bat_path}")
                subprocess.Popen(
                    ["explorer.exe", bat_path],
                    cwd=os.path.dirname(exe_path),
                )
                if handler and not was_running:
                    handler.mark_started_instance(instance_name=None)
                ok = True
            except Exception as exc:
                self._log(f"Ошибка запуска Everything из мастера: {exc}")
            QTimer.singleShot(0, lambda: self._finish_everything_launch(ok))

        threading.Thread(target=_task, daemon=True).start()

    def _launch_everything_via_ahk(self):
        if self._everything_launch_in_progress:
            return
        self._launch_everything_for_indexing(
            status_label="Запускаю сервис через AHK..."
        )
        if self._everything_launch_in_progress:
            threading.Thread(target=self._run_everything_helper, daemon=True).start()

    def _finish_everything_launch(self, ok: bool):
        self._everything_launch_in_progress = False
        self.everything_launch_btn.setEnabled(True)
        if not ok:
            self.everything_status_label.setText("Не удалось запустить Everything.")
            return
        self.everything_status_label.setText(
            "Запрос отправлен. Проверяю запуск Everything..."
        )
        QTimer.singleShot(1500, self._verify_everything_launch)

    def _verify_everything_launch(self):
        handler = getattr(self.assistant, "search_handler", None)
        if handler and handler.is_everything_process_running():
            self._bring_everything_window()
            self.everything_status_label.setText(
                "Everything запущен. Окно можно закрыть - иконка останется в трее."
            )
            self.assistant.warmup_everything_async()
            return
        self.everything_status_label.setText(
            "Everything не запустился. Проверьте install_service.log."
        )
        QTimer.singleShot(1500, self._bring_everything_window)

    def _run_everything_helper(self) -> bool:
        handler = getattr(self.assistant, "search_handler", None)
        exe_path = getattr(handler, "everything_path", "") if handler else ""
        exe_dir = os.path.dirname(exe_path) if exe_path else ""
        candidates = []
        if exe_dir:
            candidates.append(os.path.join(exe_dir, "everything_service_helper.exe"))
        candidates.append(os.path.join(self._exe_dir, "everything_service_helper.exe"))
        candidates.append(
            os.path.join(self._exe_dir, "_internal", "Everything", "everything_service_helper.exe")
        )
        for path in candidates:
            if path and os.path.exists(path):
                try:
                    self._log(f"Запуск everything_service_helper.exe: {path}")
                    subprocess.Popen(
                        [path],
                        cwd=os.path.dirname(path),
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    return True
                except Exception as exc:
                    self._log(f"Ошибка запуска everything_service_helper.exe: {exc}")
                    return False
        self._log("everything_service_helper.exe не найден.")
        return False

    def _bring_everything_window(self):
        if os.name != "nt":
            return False
        try:
            user32 = self._get_user32()
        except Exception as exc:
            self._log(f"Не удалось инициализировать WinAPI: {exc}")
            return False
        hwnd = self._find_everything_main_window(user32)
        if not hwnd:
            return False
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        return True

    def _get_user32(self):
        user32 = ctypes.WinDLL("user32", use_last_error=True)
        user32.FindWindowW.restype = wintypes.HWND
        user32.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        user32.FindWindowExW.restype = wintypes.HWND
        user32.FindWindowExW.argtypes = [
            wintypes.HWND,
            wintypes.HWND,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
        ]
        user32.EnumWindows.restype = wintypes.BOOL
        user32.EnumWindows.argtypes = [
            ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM),
            wintypes.LPARAM,
        ]
        user32.GetClassNameW.restype = ctypes.c_int
        user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.GetWindowTextLengthW.restype = ctypes.c_int
        user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
        user32.GetWindowTextW.restype = ctypes.c_int
        user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        user32.SendMessageW.restype = wintypes.LRESULT
        user32.SendMessageW.argtypes = [
            wintypes.HWND,
            wintypes.UINT,
            wintypes.WPARAM,
            wintypes.LPARAM,
        ]
        user32.GetDlgItem.restype = wintypes.HWND
        user32.GetDlgItem.argtypes = [wintypes.HWND, ctypes.c_int]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.ShowWindow.restype = wintypes.BOOL
        user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        return user32

    def _get_window_text(self, user32, hwnd) -> str:
        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buffer = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buffer, len(buffer))
        return buffer.value

    def _get_class_name(self, user32, hwnd) -> str:
        buffer = ctypes.create_unicode_buffer(256)
        if user32.GetClassNameW(hwnd, buffer, len(buffer)) == 0:
            return ""
        return buffer.value

    def _find_everything_main_window(self, user32) -> int:
        found = {"hwnd": 0}
        wnd_enum = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        def enum_proc(hwnd, _):
            title = self._get_window_text(user32, hwnd)
            if not title or "Everything" not in title:
                return True
            class_name = self._get_class_name(user32, hwnd)
            if class_name == "#32770":
                return True
            found["hwnd"] = int(hwnd)
            return False

        enum_cb = wnd_enum(enum_proc)
        user32.EnumWindows(enum_cb, 0)
        return found["hwnd"]
