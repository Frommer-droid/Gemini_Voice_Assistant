import os
import re
from typing import Callable, List, Optional, Tuple

from app.services.everything_es import run_es_search
from app.services.everything_file_filters import detect_file_filter
from app.services.everything_gemini import normalize_search_query
from app.services.everything_match import (
    build_regex_pattern,
    select_best_path,
    strip_punctuation,
)
from app.services.everything_paths import (
    ES_EXE_PATH,
    EVERYTHING_EXE_PATH,
    format_path_for_log,
)
from app.services.everything_runtime import EverythingRuntime

FOLDER_KEYWORDS = ("папк", "каталог", "директори")
FILE_KEYWORD = "файл"
ALL_DRIVES_PHRASES = ("везде", "по всем дискам", "на всех дисках")


def _normalize_intent_text(text: str) -> str:
    return " ".join(strip_punctuation(text).lower().split())


def _has_folder_intent(norm_text: str) -> bool:
    return any(keyword in norm_text for keyword in FOLDER_KEYWORDS)


def _has_file_intent(norm_text: str) -> bool:
    return FILE_KEYWORD in norm_text


def _has_all_drives_intent(norm_text: str) -> bool:
    if any(phrase in norm_text for phrase in ALL_DRIVES_PHRASES):
        return True
    return bool(re.search(r"\bна\s+диске\s+[a-zа-я]\s+или\s+[a-zа-я]\b", norm_text))


class EverythingSearchHandler(EverythingRuntime):
    """
    Вынесенная логика голосового поиска через Everything (es.exe).
    Сценарий:
    1. Проверяем, что команда начинается с формы слова <найди>.
    2. Отправляем сырой текст в Gemini 2.5 Flash для нормализации и исправления опечаток.
    3. Генерируем регулярное выражение по правилам заказчика.
    4. Запускаем es.exe с флагами /ad (папки) или /a-d (файлы) и ограничением результатов.
    5. Возвращаем найденные пути.
    """

    def __init__(
        self,
        log_func: Callable[[str], None],
        es_path: str = ES_EXE_PATH,
        everything_path: str = EVERYTHING_EXE_PATH,
    ):
        super().__init__(log_func, es_path=es_path, everything_path=everything_path)
        self._trigger_re = re.compile(r"^\s*найд[а-яa-z]*", flags=re.IGNORECASE)

    def looks_like_search(self, text: str) -> bool:
        """Быстрая проверка наличия триггера, чтобы не дергать Gemini без повода."""
        if not isinstance(text, str):
            return False
        return bool(self._trigger_re.match(text.strip().lower()))

    def handle_voice_command(
        self,
        text: str,
        client,
        status_cb: Optional[Callable[[str, str, bool], None]] = None,
        colors: Optional[dict] = None,
        open_cb: Optional[Callable[[str], None]] = None,
        cancel_check: Optional[Callable[[], bool]] = None,
    ) -> Tuple[bool, List[str]]:
        """
        Возвращает (handled, paths).
        handled = True, если это команда <найди> и мы её обработали (даже если результаты пустые).
        paths - список найденных путей.
        """
        if not self.looks_like_search(text):
            return False, []
        if cancel_check and cancel_check():
            self.log("Отмена поиска пользователем.")
            return True, []

        colors = colors or {}
        accent = colors.get("accent", "#3AE2CE")
        warning = colors.get("warning", "#BF8255")

        if status_cb:
            status_cb("Обрабатываю голосовой поиск...", accent, True)

        query = normalize_search_query(self.log, client, text)
        norm_text = _normalize_intent_text(text)
        wants_folder = _has_folder_intent(norm_text)
        wants_file = _has_file_intent(norm_text)
        wants_all_drives = _has_all_drives_intent(norm_text)
        if cancel_check and cancel_check():
            self.log("Отмена поиска пользователем.")
            return True, []
        if not query:
            if status_cb:
                status_cb("Не смог распознать запрос поиска", warning, False)
            return True, []

        if wants_all_drives:
            query.drive = None

        # Определяем категорию файлов по исходному тексту или имени
        ext_filter = detect_file_filter(norm_text) or detect_file_filter(
            strip_punctuation(query.name)
        )

        if wants_folder:
            query.target_type = "folder"
        elif ext_filter or wants_file:
            query.target_type = "file"

        if query.target_type not in ("folder", "file"):
            self.log(
                f"Команда поиска пропущена: неподдерживаемый тип {query.target_type}"
            )
            return True, []

        if ext_filter:
            if query.target_type == "file":
                query.extensions = ext_filter
            else:
                self.log(
                    "Запрошена папка - игнорируем фильтр по расширениям, чтобы не переключаться на поиск файлов."
                )

        pattern = build_regex_pattern(query.name, query.target_type) if query.name else None
        if not pattern and not query.extensions:
            if status_cb:
                status_cb("Не получилось построить запрос поиска", warning, False)
            return True, []

        if not os.path.exists(self.es_path):
            path_label = format_path_for_log(self.es_path) or str(self.es_path)
            self.log(f"es.exe не найден по пути: {path_label}")
            if status_cb:
                status_cb("Поисковик Everything не найден", warning, False)
            return True, []

        if cancel_check and cancel_check():
            self.log("Отмена поиска пользователем.")
            return True, []

        if not self.ensure_everything_running(timeout_s=8.0):
            if self.last_es_error:
                self.log(f"Everything недоступен: {self.last_es_error}")
            else:
                self.log("Everything недоступен, поиск невозможен.")
            if status_cb:
                status_cb("Поисковик Everything недоступен", warning, False)
            return True, []

        paths = run_es_search(self.log, self.es_path, self.instance_name, pattern, query)

        if not paths:
            self.log(f"Ничего не найдено для '{query.name}' (шаблон: {pattern})")
            if status_cb:
                status_cb(f"Не найдено: {query.name}", warning, False)
            return True, []

        best_path = select_best_path(paths, query.name, drive=query.drive, log_func=self.log)
        if not best_path:
            self.log("Не удалось выбрать подходящий результат: имя отсутствует или нет совпадений.")
            if status_cb:
                status_cb(f"Не найдено: {query.name}", warning, False)
            return True, []

        top = best_path
        if status_cb:
            disk_info = f" на диске {query.drive.upper()}" if query.drive else ""
            status_cb(f"Нашёл {query.target_type}: {query.name}{disk_info}", accent, False)

        if open_cb:
            try:
                if cancel_check and cancel_check():
                    self.log("Отмена открытия результата поиска пользователем.")
                    return True, paths
                open_cb(top)
            except Exception as e:
                path_label = format_path_for_log(top) or str(top)
                self.log(f"Ошибка открытия результата '{path_label}': {e}")
        return True, paths
