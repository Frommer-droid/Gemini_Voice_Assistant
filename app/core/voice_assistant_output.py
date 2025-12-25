# -*- coding: utf-8 -*-
"""Вывод результата и вспомогательные операции."""

import os
import re
import subprocess
import sys
import traceback

from app.core.app_config import COLORS, HISTORY_FILE, LOG_FILE
from app.utils import logging_utils
from app.utils.logging_utils import log_message, reset_logger


class VoiceAssistantOutputMixin:
    def _should_open_logs_for_status(self, txt: str) -> bool:
        text = (txt or "").lower()
        failure_markers = [
            "команда не найдена",
            "ошибка выполнения",
            "ошибка браузера",
            "не удалось открыть",
            "не смог открыть",
            "ошибка открытия",
            "не смог распознать запрос поиска",
            "не получилось построить запрос поиска",
            "поисковик everything не найден",
            "ошибка поиска everything",
            "не найдено:",
            "не нашел",
            "не нашёл",
        ]
        return any(marker in text for marker in failure_markers)

    def show_status(self, txt, color, spinning=False):
        if self.ui_signals:
            self.ui_signals.status_changed.emit(txt, color, spinning)
            if self._should_open_logs_for_status(txt):
                self.ui_signals.request_show_logs.emit()

    def update_volume_indicator(self, volume_level):
        if self.ui_signals:
            normalized = min(100, max(0, int((volume_level / 5000) * 100)))
            self.ui_signals.volume_changed.emit(normalized)

    def load_history_to_combo(self):
        """Загрузка истории для комбобокса."""
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
                        display = (
                            f"{timestamp} - "
                            f"{display_text[:50]}{'...' if len(display_text) > 50 else ''}"
                        )
                        items.append((display, text))
        except Exception as e:
            log_message(f"Ошибка загрузки истории: {e}")

        return items

    def clear_log_file(self, silent: bool = False):
        """Очистка файла логов; silent=True - без служебной записи в лог."""
        try:
            # Закрываем и удаляем текущие обработчики
            for handler in list(logging_utils.logger.handlers):
                handler.close()
                logging_utils.logger.removeHandler(handler)

            # Перезаписываем файл
            with open(LOG_FILE, "w", encoding="utf-8", errors="replace") as f:
                f.write("")

            # Переинициализация логгера
            reset_logger()
            if not silent:
                log_message("Лог-файл очищен")
        except Exception as e:
            # Используем print, т.к. логгер может быть недоступен
            print(f"Ошибка очистки логов: {e}")

    def clear_history_file(self):
        """Очистка файла истории."""
        try:
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                f.write("")
            log_message("Файл истории очищен")
            if self.ui_signals:
                self.ui_signals.history_updated.emit()
        except Exception as e:
            log_message(f"Ошибка очистки файла истории: {e}")

    def set_autostart(self, enabled):
        """Управление автозагрузкой через папку Startup."""
        try:
            startup_folder = os.path.join(
                os.environ["APPDATA"],
                r"Microsoft\Windows\Start Menu\Programs\Startup",
            )

            shortcut_path = os.path.join(startup_folder, "Gemini_Voice_Assistant.lnk")

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
oLink.Description = "Gemini Voice Assistant"
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
