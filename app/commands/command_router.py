# -*- coding: utf-8 -*-
"""
Маршрутизация голосовых команд: сайты, запуск приложений и поиск Everything.
"""

import os
import re
import subprocess
import threading
import traceback
import webbrowser

from PySide6.QtWidgets import QMessageBox

from app.core.app_config import (
    COLORS,
    DANGEROUS_COMMAND_PATTERNS,
    LAUNCH_COMMANDS,
    WEBSITE_URLS,
)
from app.utils.logging_utils import log_message


class CommandRouter:
    def __init__(self, assistant, log_func=log_message):
        self.assistant = assistant
        self.log = log_func

    def handle_website_command(self, text):
        """
        Проверяет, является ли текст командой открытия сайта.
        Если да - открывает сайт и возвращает True.
        """
        self.log(f"DEBUG: Проверка на команду сайта. Входной текст: '{text}'")

        text_lower = text.strip().lower()
        # Заменяем любую пунктуацию на пробелы и нормализуем пробелы
        # "Открой, гугл!" -> "открой гугл"
        text_lower = re.sub(r"[^\w\s]", " ", text_lower)
        text_lower = " ".join(text_lower.split())

        self.log(f"DEBUG: Очищенный текст: '{text_lower}'")

        # Ключевые слова для навигации - только формы слова "открой"
        triggers = ["открой", "открыть", "откроем", "открывай"]

        triggered = False
        command_body = ""

        for trigger in triggers:
            if text_lower.startswith(trigger + " "):
                triggered = True
                command_body = text_lower[len(trigger) :].strip()
                self.log(
                    f"DEBUG: Сработал триггер '{trigger}'. Тело команды: '{command_body}'"
                )
                break

        # Логируем для отладки, если не сработало, но похоже на команду
        if not triggered:
            self.log(f"DEBUG: Триггер не сработал. Проверял триггеры: {triggers}")
            if any(t in text_lower for t in triggers):
                self.log(f"Похоже на команду, но не сработало: '{text_lower}'")

        if not triggered:
            return False

        cancel_seq = self.assistant._get_cancel_seq()
        if self.assistant._is_cancelled(cancel_seq):
            self.log("Команда открытия сайта отменена пользователем.")
            return True

        self.log(f"Распознана команда навигации: '{command_body}'")

        url = None
        site_name = command_body

        # 1. Прямой поиск в словаре
        if site_name in WEBSITE_URLS:
            url = WEBSITE_URLS[site_name]

        # 2. Если не нашли в словаре - спрашиваем у Gemini
        if not url:
            self.log(
                f"Сайт '{site_name}' не найден в словаре. Спрашиваю у Gemini..."
            )
            self.assistant.show_status("Поиск адреса...", COLORS["accent"], True)
            url = self._resolve_url_with_gemini(site_name)

        if self.assistant._is_cancelled(cancel_seq):
            self.log("Команда открытия сайта отменена пользователем.")
            return True

        # 3. Если Gemini не дал URL или вернул SEARCH - ищем в Яндексе
        if not url or url == "SEARCH":
            self.log(f"Gemini не вернул точный URL, поиск в Яндексе: {site_name}")
            url = f"https://yandex.ru/search/?text={site_name}"

        if self.assistant._is_cancelled(cancel_seq):
            self.log("Команда открытия сайта отменена пользователем.")
            return True

        try:
            self.log(f"Открываю URL: {url}")
            webbrowser.open(url)
            self.assistant.show_status(f"Открываю: {site_name}", COLORS["accent"], False)
            self.assistant.play_sound("start")  # Звук успеха

            # Очищаем буфер, так как команда выполнена
            self.assistant.audio_buffer.clear()

            # Сворачиваем окно обратно
            if self.assistant.ui_signals:
                self.assistant.ui_signals.request_hide_window.emit()

            threading.Timer(
                2.0,
                lambda: self.assistant.show_status(
                    "Готов к работе", COLORS["accent"], False
                ),
            ).start()
            return True
        except Exception as e:
            self.log(f"Ошибка открытия URL: {e}")
            self.assistant.show_status("Ошибка браузера", COLORS["btn_warning"], False)
            return False

    def handle_launch_command(self, text):
        """
        Проверяет, является ли текст командой запуска программы/команды.
        Если да - выполняет команду и возвращает True.
        """
        self.log(f"DEBUG: Проверка на команду запуска. Входной текст: '{text}'")

        text_lower = text.strip().lower()
        # Заменяем любую пунктуацию на пробелы и нормализуем пробелы
        text_lower = re.sub(r"[^\w\s]", " ", text_lower)
        text_lower = " ".join(text_lower.split())

        self.log(f"DEBUG: Очищенный текст: '{text_lower}'")

        # Ключевые слова для запуска программ - только формы слова "запусти"
        triggers = [
            "запусти",
            "запустить",
            "запуск",
            "запустим",
            "запускай",
            "запускаю",
        ]

        triggered = False
        command_body = ""
        admin_requested = False

        for trigger in triggers:
            if text_lower.startswith(trigger + " "):
                triggered = True
                command_body = text_lower[len(trigger) :].strip()
                self.log(
                    f"DEBUG: Сработал триггер '{trigger}'. Тело команды: '{command_body}'"
                )
                break

        if not triggered:
            self.log(f"DEBUG: Триггер не сработал. Проверял триггеры: {triggers}")
            return False

        cancel_seq = self.assistant._get_cancel_seq()
        if self.assistant._is_cancelled(cancel_seq):
            self.log("Команда запуска отменена пользователем.")
            return True

        # Проверяем запрос на запуск с правами администратора
        admin_markers = [
            "от имени администратора",
            "админ",
            "админка",
            "администратор",
            "с правами админа",
            "с правами администратора",
        ]
        for marker in admin_markers:
            if marker in command_body:
                admin_requested = True
                command_body = command_body.replace(marker, " ")
        command_body = " ".join(command_body.split())

        self.log(
            f"Распознан запрос запуска: '{command_body}', admin={admin_requested}"
        )

        command = None
        command = None
        command = None
        program_name = command_body

        # 1. Прямой поиск в словаре
        if program_name in LAUNCH_COMMANDS:
            command = LAUNCH_COMMANDS[program_name]
            self.log(f"Команда найдена в словаре: '{command}'")

        # 2. Если не нашли в словаре - спрашиваем у Gemini
        if not command:
            self.log(
                f"Команда '{program_name}' не найдена в словаре. Спрашиваю у Gemini..."
            )
            self.assistant.show_status("Определение команды...", COLORS["accent"], True)
            command = self._resolve_command_with_gemini(program_name, cancel_seq)

        if self.assistant._is_cancelled(cancel_seq):
            self.log("Команда запуска отменена пользователем.")
            return True

        # 3. Если Gemini не дал команду или вернул UNKNOWN
        if not command or command == "UNKNOWN":
            self.log(f"Не удалось определить команду для: {program_name}")
            self.assistant.show_status(
                f"Команда не найдена: {program_name}", COLORS["btn_warning"], False
            )
            self.assistant.play_sound("error")
            threading.Timer(
                2.0,
                lambda: self.assistant.show_status(
                    "Готов к работе", COLORS["accent"], False
                ),
            ).start()
            if self.assistant.ui_signals:
                self.assistant.ui_signals.request_hide_window.emit()
            return True  # Команда обработана, но не выполнена

        # 4. Проверка на опасность
        if self._is_dangerous_command(command):
            self.log(
                f"ПРЕДУПРЕЖДЕНИЕ: Обнаружена потенциально опасная команда: {command}"
            )
            # Показываем диалог подтверждения
            if not self._show_command_confirmation_dialog(command):
                self.log(f"DANGEROUS COMMAND REJECTED: {command}")
                self.assistant.show_status(
                    "Команда отменена", COLORS["btn_warning"], False
                )
                self.assistant.play_sound("error")
                if self.assistant.ui_signals:
                    self.assistant.ui_signals.request_hide_window.emit()
                threading.Timer(
                    2.0,
                    lambda: self.assistant.show_status(
                        "Готов к работе", COLORS["accent"], False
                    ),
                ).start()
                return True
            else:
                self.log(f"DANGEROUS COMMAND CONFIRMED: {command}")

        if self.assistant._is_cancelled(cancel_seq):
            self.log("Команда запуска отменена пользователем.")
            return True

        # 5. Выполнение команды
        try:
            self.log(f"COMMAND EXECUTED: {command} (admin={admin_requested})")

            # Очищаем префикс DANGER: если он есть
            command = command.replace("DANGER:", "").strip()

            # Запуск с повышением прав при запросе
            if admin_requested and not command.startswith("ms-settings:"):
                parts = command.split()
                exe = parts[0]
                args = " ".join(parts[1:])
                if args:
                    command = (
                        'powershell -Command "Start-Process \\"%s\\" '
                        '-ArgumentList \\"%s\\" -Verb RunAs"'
                        % (exe, args)
                    )
                else:
                    command = (
                        'powershell -Command "Start-Process \\"%s\\" -Verb RunAs"'
                        % exe
                    )

            # Запуск команды
            if command.startswith("ms-settings:"):
                # Специальная обработка для настроек Windows
                os.startfile(command)
            else:
                # Обычный запуск через subprocess
                subprocess.Popen(command, shell=True)

            self.assistant.show_status(
                f"Запущено: {program_name}", COLORS["accent"], False
            )
            self.assistant.play_sound("start")  # Звук успеха

            # Очищаем буфер, так как команда выполнена
            self.assistant.audio_buffer.clear()

            # Сворачиваем окно обратно
            if self.assistant.ui_signals:
                self.assistant.ui_signals.request_hide_window.emit()

            threading.Timer(
                2.0,
                lambda: self.assistant.show_status(
                    "Готов к работе", COLORS["accent"], False
                ),
            ).start()
            return True
        except Exception as e:
            self.log(f"Ошибка выполнения команды '{command}': {e}")
            self.assistant.show_status("Ошибка выполнения", COLORS["btn_warning"], False)
            self.assistant.play_sound("error")
            if self.assistant.ui_signals:
                self.assistant.ui_signals.request_hide_window.emit()
            threading.Timer(
                2.0,
                lambda: self.assistant.show_status(
                    "Готов к работе", COLORS["accent"], False
                ),
            ).start()
            return False

    def handle_everything_search(self, text):
        """
        Обрабатывает голосовые команды на поиск через Everything (es.exe).
        Возвращает True, если команда была распознана (даже без результатов).
        """
        try:
            cancel_seq = self.assistant._get_cancel_seq()
            handled, paths = self.assistant.search_handler.handle_voice_command(
                text=text,
                client=self.assistant.client,
                status_cb=self.assistant.show_status,
                colors={"accent": COLORS["accent"], "warning": COLORS["btn_warning"]},
                open_cb=self._open_path_safely,
                cancel_check=lambda: self.assistant._is_cancelled(cancel_seq),
            )
            if handled:
                if self.assistant._is_cancelled(cancel_seq):
                    self.log("Поиск Everything отменен пользователем.")
                    return True
                if paths:
                    self.assistant.play_sound("start")
                    self.assistant.audio_buffer.clear()
                # Сворачиваем окно независимо от успеха
                if self.assistant.ui_signals:
                    self.assistant.ui_signals.request_hide_window.emit()
                    self.assistant.ui_signals.request_refresh_everything.emit()
            return handled
        except Exception as e:
            self.log(f"Ошибка обработки поиска через Everything: {e}")
            self.log(traceback.format_exc())
            self.assistant.show_status(
                "Ошибка поиска Everything", COLORS["btn_warning"], False
            )
            return False

    def _open_path_safely(self, path):
        """Открывает файл/папку через ОС с логированием ошибок."""
        try:
            os.startfile(path)
        except Exception as e:
            self.log(f"Ошибка открытия пути '{path}': {e}")
            self.assistant.show_status(
                "Не удалось открыть найденное", COLORS["btn_warning"], False
            )

    def _resolve_command_with_gemini(self, description, cancel_seq=None):
        """
        Использует Gemini для определения команды по описанию.
        Возвращает команду или 'UNKNOWN' если не уверен.
        """
        cancel_check = None
        if cancel_seq is not None:
            def cancel_check():
                return self.assistant._is_cancelled(cancel_seq)
        return self.assistant.gemini_manager.resolve_command(
            description, cancel_check=cancel_check
        )

    def _is_dangerous_command(self, command):
        """
        Проверяет, является ли команда потенциально опасной.
        Возвращает True если команда опасна.
        """
        # Проверка префикса от Gemini
        if command.startswith("DANGER:"):
            return True

        # Проверка по паттернам
        command_lower = command.lower()
        for pattern in DANGEROUS_COMMAND_PATTERNS:
            if re.search(pattern, command_lower):
                return True

        return False

    def _show_command_confirmation_dialog(self, command):
        """
        Показывает диалог подтверждения для опасной команды.
        Возвращает True если пользователь подтвердил выполнение.
        """
        # Убираем префикс DANGER: для отображения
        display_command = command.replace("DANGER:", "").strip()

        msg_box = QMessageBox()
        msg_box.setWindowTitle("?? Подтверждение опасной команды")
        msg_box.setText(
            f"Команда может быть опасна:\n\n{display_command}\n\nВыполнить?"
        )
        msg_box.setIcon(QMessageBox.Warning)
        msg_box.setStandardButtons(QMessageBox.Yes | QMessageBox.No)
        msg_box.setDefaultButton(QMessageBox.No)

        result = msg_box.exec()
        return result == QMessageBox.Yes

    def _resolve_url_with_gemini(self, description):
        """
        Использует Gemini для определения URL по описанию.
        Возвращает URL или 'SEARCH' если не уверен.
        """
        return self.assistant.gemini_manager.resolve_url(description)
