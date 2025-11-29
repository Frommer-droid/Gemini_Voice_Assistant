import json
import locale
import os
import re
import socket
import subprocess
import tempfile
import traceback
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Callable, List, Optional, Tuple

from google.genai import types

try:
    from google.genai import errors as genai_errors
except Exception:
    genai_errors = None

try:
    import httpx
except Exception:
    httpx = None

from everything_file_filters import detect_file_filter

# Путь к консольной утилите Everything ES CLI
ES_EXE_PATH = r"C:\Program Files\Everything\ES-1.1.0.30.x64\es.exe"


@dataclass
class SearchQuery:
    trigger: str
    target_type: str  # folder | file | unknown
    name: str
    drive: Optional[str]  # 'c', 'd' или None
    extensions: Optional[str] = None  # список расширений для ext: фильтра


class EverythingSearchHandler:
    """
    Вынесенная логика голосового поиска через Everything (es.exe).
    Сценарий:
    1. Проверяем, что команда начинается с формы слова «найди».
    2. Отправляем сырой текст в Gemini 2.5 Flash для нормализации и исправления опечаток.
    3. Генерируем регулярное выражение по правилам заказчика.
    4. Запускаем es.exe с флагами /ad (папки) или /a-d (файлы) и ограничением результатов.
    5. Возвращаем найденные пути.
    """

    def __init__(self, log_func: Callable[[str], None], es_path: str = ES_EXE_PATH):
        self.log = log_func
        self.es_path = es_path
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
    ) -> Tuple[bool, List[str]]:
        """
        Возвращает (handled, paths).
        handled = True, если это команда «найди» и мы её обработали (даже если результаты пустые).
        paths — список найденных путей.
        """
        if not self.looks_like_search(text):
            return False, []

        colors = colors or {}
        accent = colors.get("accent", "#3AE2CE")
        warning = colors.get("warning", "#BF8255")

        if status_cb:
            status_cb("Обрабатываю голосовой поиск...", accent, True)

        query = self._normalize_with_gemini(client, text)
        if not query:
            if status_cb:
                status_cb("Не смог распознать запрос поиска", warning, False)
            return True, []

        if query.target_type not in ("folder", "file"):
            self.log(f"Команда поиска пропущена: неподдерживаемый тип {query.target_type}")
            return True, []

        # Определяем категорию файлов по исходному тексту или имени
        ext_filter = detect_file_filter(self._strip_punctuation(text)) or detect_file_filter(
            self._strip_punctuation(query.name)
        )
        if ext_filter:
            if query.target_type == "file":
                query.extensions = ext_filter
            else:
                self.log(
                    "Запрошена папка — игнорируем фильтр по расширениям, чтобы не переключаться на поиск файлов."
                )

        pattern = self._build_regex_pattern(query.name, query.target_type) if query.name else None
        if not pattern and not query.extensions:
            if status_cb:
                status_cb("Не получилось построить запрос поиска", warning, False)
            return True, []

        if not os.path.exists(self.es_path):
            self.log(f"es.exe не найден по пути: {self.es_path}")
            if status_cb:
                status_cb("Поисковик Everything не найден", warning, False)
            return True, []

        paths = self._run_es_search(pattern, query)

        if not paths:
            self.log(f"Ничего не найдено для '{query.name}' (шаблон: {pattern})")
            if status_cb:
                status_cb(f"Не найдено: {query.name}", warning, False)
            return True, []

        best_path = self._select_best_path(paths, query.name, drive=query.drive)
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
                open_cb(top)
            except Exception as e:
                self.log(f"Ошибка открытия результата '{top}': {e}")
        return True, paths

    def _normalize_with_gemini(self, client, text: str) -> Optional[SearchQuery]:
        """Нормализуем запрос через Gemini с фолбэком и аккуратным логом."""
        if not client:
            self.log("Gemini не инициализирован, пропускаю обработку поиска")
            return None

        prompt = f"""
 Ты помогаешь голосовому ассистенту готовить запросы для поиска через Everything ES CLI (es.exe).
 После триггера «найди папку …» пользователь может простыми словами описывать, как выглядит имя, включая указания вроде
 «два ноля потом нижнее подчеркивание и слово развитие», «два слова и оба на английском».
 Нужно превратить описание в итоговое имя и вернуть ТОЛЬКО один объект JSON одной строкой без пояснений.

 Формат JSON:
 {{
   "trigger": "найди",            // исходное триггерное слово в нормальной форме, если оно есть, иначе пустая строка
   "target_type": "folder|file|unknown",
   "name": "готовое имя файла/папки без слов типа 'папка' и 'на диске ...'",
   "drive": "буква_диска_в_нижнем_регистре_или_all" // например "d". Если не сказано, верни "all".
 }}

 Правила:
 1. Считай командой только фразы, начинающиеся с формы слова «найди/найдите/найти/найдём/найдем».
 2. Тип:
    - «папка/каталог/директорию» — target_type = "folder";
    - «файл/документ» — target_type = "file";
    - иначе по умолчанию "folder".
 3. Имя: возьми только основное название, исправь опечатки, сохрани порядок.
    - ВСЕГДА соблюдай явные указания пользователя (язык, разделители, состав): «два/три слова», «оба/все на английском/русском», «нижнее подчеркивание», «пробел», «цифра», «слить слова», и т.п.
    - Не придумывай ничего сверх указаний, не исправляй формат, если он задан.
    - Примеры преобразования:
      • «два ноля потом нижнее подчеркивание и слово развитие» → "00_Развитие"
      • «portable soft» → "portable soft"
      • «два слова и оба на английском языке: youtube видео» → "youtube video"
      • «мои сайты, только английскими словами и разделенные нижним подчеркиванием» → "my_sites"
    - Удали служебные части «папку», «на диске ...», «слова» и т.п.
 4. Диск: вытащи букву после фразы «на диске х» → "d". Нет буквы — "all".
 5. Если это не команда поиска, верни trigger:"" и target_type:"unknown", остальные поля пустые.

 Примеры:
 Ввод: "найди папку откудо береться оптимязм на диске д"
 Вывод: {{"trigger":"найди","target_type":"folder","name":"откуда берётся оптимизм","drive":"d"}}
 Ввод: "найди папку youtube видео два слова и оба на английском языке на диске д"
 Вывод: {{"trigger":"найди","target_type":"folder","name":"youtube video","drive":"d"}}
 Ввод: "найди папку portable soft"
 Вывод: {{"trigger":"найти","target_type":"folder","name":"portable soft","drive":"all"}}
 Ввод: "найди папку на диске d два ноля потом нижнее подчеркивание и слово развитие"
 Вывод: {{"trigger":"найди","target_type":"folder","name":"00_Развитие","drive":"d"}}

 Текст запроса: "{text}"
 """

        candidates = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3-pro-preview"]
        attempted = set()
        last_error = None

        for model_name in candidates:
            if model_name in attempted:
                continue
            attempted.add(model_name)
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=types.GenerateContentConfig(temperature=0.1),
                )
                raw = (getattr(response, "text", "") or "").strip()
                self.log(f"Gemini нормализация поиска ({model_name}), ответ: {raw}")
                data = self._extract_json(raw)
                if not data:
                    self.log("Не удалось распарсить JSON от Gemini для поиска")
                    return None

                trigger = (data.get("trigger") or "").strip().lower()
                if not trigger:
                    return None

                target_type = (data.get("target_type") or "unknown").strip().lower()
                name = (data.get("name") or "").strip()
                drive = (data.get("drive") or "").strip().lower()
                if not name:
                    return None

                drive = drive or None
                if drive and len(drive) == 1 and drive.isalpha():
                    drive = drive.lower()
                else:
                    drive = None if drive == "all" or not drive else drive

                return SearchQuery(
                    trigger=trigger,
                    target_type=target_type,
                    name=name,
                    drive=drive,
                )
            except Exception as e:
                last_error = e
                short = self._short_error(e)
                self.log(f"Ошибка Gemini при нормализации ({model_name}): {short}")
                if not self._should_try_fallback(e, attempted, model_name, candidates):
                    break

        if last_error:
            self.log(traceback.format_exc())
        return None

    def _short_error(self, error: Exception) -> str:
        """Сокращает шумные HTML/stacktrace ошибки для логов."""
        txt = str(error) if error else ""
        txt = re.sub(r"\s+", " ", txt).strip()
        return txt[:400]

    def _should_try_fallback(
        self, error: Exception, attempted: set, current_model: str, candidates: list
    ) -> bool:
        """Решает, стоит ли переходить на следующую модель после ошибки."""
        retryable_codes = {403, 404, 408, 409, 429, 500, 502, 503}
        if genai_errors:
            if isinstance(error, genai_errors.ClientError):
                code = getattr(error, "status_code", None) or getattr(error, "code", None)
                if code in retryable_codes:
                    return True
            if isinstance(error, genai_errors.ServerError):
                return True

        if httpx and isinstance(error, (httpx.TransportError, httpx.TimeoutException)):
            return True

        if isinstance(error, (socket.timeout, ConnectionError)):
            return True

        return len(attempted) < len(candidates)

    def _extract_json(self, text: str) -> Optional[dict]:
        """Безопасно извлекает JSON даже если Gemini обернул его в текст."""
        try:
            return json.loads(text)
        except Exception:
            pass

        match = re.search(r"\{.*\}", text, flags=re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except Exception:
            return None

    def _build_regex_pattern(self, name: str, target_type: str) -> Optional[str]:
        """Создаёт регэксп по правилам из ТЗ для имени файла/папки."""
        if not name:
            return None

        cleaned_name = self._strip_punctuation(name)
        words = self._tokenize_name(cleaned_name)
        if not words:
            return None

        if len(words) == 1:
            word = words[0]
            if len(word) < 2:
                return None
            prefix = word[:3] if len(word) >= 3 else word
            suffix = word[-2:] if len(word) >= 2 else word
            body = f"{prefix}[\\s\\S]*?{suffix}"
        else:
            def _chunk(w: str) -> str:
                if len(w) <= 3:
                    return w
                return w[:4]

            chunks = [_chunk(w) for w in words]
            # Между каждым словом ставим [\s\S]*?, последнее слово завершаем .+
            body = "[\\s\\S]*?".join(chunks)
            body = f"{body}.+"

        return body

    def _run_es_search(self, pattern: Optional[str], query: SearchQuery) -> List[str]:
        """
        Запускает es.exe и читает результаты из временного файла в UTF-8 (с BOM),
        чтобы избежать проблем с кодировками stdout. Делает два запроса:
        1) regex (фаззи по правилам)
        2) прямой текстовый (для точных совпадений вроде 'Развитие' или 'Portable Soft')
        """
        base_args = [self.es_path]
        if query.drive:
            base_args += ["-path", f"{query.drive}:\\"]

        type_flag = "/ad" if query.target_type == "folder" else "/a-d" if query.target_type == "file" else None
        searches = []

        # Добавляем расширения как фильтр ext:
        ext_filter = f"ext:{query.extensions}" if query.extensions else ""

        if pattern:
            regex_args = base_args + ["-r", pattern, "-n", "30", "-sort", "name-ascending"]
            if ext_filter:
                regex_args.append(ext_filter)
            if type_flag:
                regex_args.append(type_flag)
            searches.append(("regex", regex_args))

        # Прямой поиск: имя + ext-фильтр (или только ext-фильтр)
        plain_terms = []
        if query.name:
            plain_terms.append(query.name)
        if ext_filter:
            plain_terms.append(ext_filter)
        search_text = " ".join(plain_terms) if plain_terms else ext_filter
        if not search_text.strip():
            search_text = ""

        plain_args = base_args + ([search_text] if search_text else []) + ["-n", "30", "-sort", "name-ascending"]
        if type_flag:
            plain_args.append(type_flag)
        searches.append(("plain", plain_args))

        all_lines: List[str] = []
        for label, args in searches:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as tmp:
                    tmp_path = tmp.name
                export_args = args + ["-export-txt", tmp_path, "-utf8-bom"]
                self.log(f"Выполняю поиск через es.exe ({label}): {export_args}")

                result = subprocess.run(export_args, capture_output=True, check=False)
            except Exception as e:
                self.log(f"Ошибка запуска es.exe ({label}): {e}")
                self.log(traceback.format_exc())
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                continue

            lines: List[str] = []
            if tmp_path and os.path.exists(tmp_path):
                try:
                    try:
                        with open(tmp_path, "r", encoding="utf-8-sig", errors="replace") as f:
                            lines = [line.strip() for line in f.readlines() if line.strip()]
                    except Exception:
                        with open(tmp_path, "r", encoding="cp1251", errors="replace") as f:
                            lines = [line.strip() for line in f.readlines() if line.strip()]
                except Exception as e:
                    self.log(f"Не удалось прочитать экспортированный файл ({label}): {e}")
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

            if not lines and result and result.stdout:
                for enc in ("utf-8", "cp1251", "cp866", "utf-16le", locale.getpreferredencoding(False) or "utf-8"):
                    try:
                        stdout = result.stdout.decode(enc, errors="replace")
                        lines = [line.strip() for line in stdout.splitlines() if line.strip()]
                        if lines:
                            break
                    except Exception:
                        continue

            all_lines.extend(lines)

        # Убираем дубликаты, сохраняя порядок
        seen = set()
        uniq_lines = []
        for line in all_lines:
            if line not in seen:
                seen.add(line)
                uniq_lines.append(line)

        self.log(f"Результаты es.exe: {len(uniq_lines)} записей")
        return uniq_lines

    # --- ВСПОМОГАТЕЛЬНОЕ СОРТИРОВАНИЕ РЕЗУЛЬТАТОВ ---
    def _normalize_text(self, text: str) -> str:
        txt = (text or "").lower().replace("ё", "е")
        return re.sub(r"[^а-яa-z0-9]+", "", txt)

    def _tokenize_name(self, name: str) -> List[str]:
        """Нормализация имени: заменяем подчёркивания/дефисы и вставляем пробелы по CamelCase."""
        with_spaces = re.sub(r"[_-]+", " ", name)
        camel_split = re.sub(r"(?<=[A-Za-zА-Яа-яЁё0-9])(?=[A-ZА-Я])", " ", with_spaces)
        normalized = camel_split.lower().replace("ё", "е")
        return [w for w in normalized.split() if w]

    def _strip_punctuation(self, name: str) -> str:
        """Убирает знаки препинания, оставляя буквы/цифры/подчёркивания и дефисы."""
        cleaned = re.sub(r"[^\w\sЁё-]+", " ", name)
        return " ".join(cleaned.split())

    def _select_best_path(self, paths: List[str], target_name: str, drive: Optional[str] = None) -> Optional[str]:
        """Выбирает лучший путь: точное совпадение по имени папки + минимальная глубина + схожесть."""
        if not paths:
            return None
        if not (target_name or "").strip():
            return None
        target_norm = self._normalize_text(target_name)
        target_clean = self._strip_punctuation(target_name)

        # Известные алиасы для системных путей (локализованные названия)
        aliases = {
            "пользователи": ["Users"],
        }
        if drive:
            alias_list = aliases.get(target_norm)
            if alias_list:
                for alias in alias_list:
                    alias_path = os.path.join(f"{drive.upper()}:\\", alias)
                    if os.path.exists(alias_path):
                        self.log(f"Прямое совпадение по алиасу: {alias_path}")
                        return alias_path

        # Приоритет: прямой путь <drive>:\<target> если существует
        if drive:
            direct_path = os.path.join(f"{drive.upper()}:\\", target_clean)
            if os.path.exists(direct_path):
                self.log(f"Прямое совпадение по диску: {direct_path}")
                return direct_path

        def score(path: str) -> int:
            base = os.path.basename(path)
            base_norm = self._normalize_text(base)
            depth = path.count(os.sep)

            ratio = SequenceMatcher(None, base_norm, target_norm).ratio() if target_norm else 0

            s = int(ratio * 100)
            if base_norm == target_norm:
                s += 180
            elif target_norm and base_norm.endswith(target_norm):
                s += 110
            elif target_norm and target_norm in base_norm:
                s += 80
            elif base_norm and base_norm in target_norm:
                s += 50

            # Чем меньше глубина (ближе к корню), тем выше
            s += max(0, 40 - depth * 2)

            # Приоритет диска
            if drive and path.lower().startswith(f"{drive.lower()}:\\"):
                s += 30

            # Чем короче путь, тем выше
            s -= len(path) // 80
            return s

        best = max(paths, key=score)
        self.log(f"Лучший кандидат для открытия: {best}")
        return best
