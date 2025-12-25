import json
import re
import socket
import traceback
from typing import Optional

from google.genai import types

try:
    from google.genai import errors as genai_errors
except Exception:
    genai_errors = None

try:
    import httpx
except Exception:
    httpx = None

from app.services.everything_models import SearchQuery


def normalize_search_query(log_func, client, text: str) -> Optional[SearchQuery]:
    """Нормализуем запрос через Gemini с фолбэком и аккуратным логом."""
    if not client:
        log_func("Gemini не инициализирован, пропускаю обработку поиска")
        return None

    prompt = f"""
 Ты помогаешь голосовому ассистенту готовить запросы для поиска через Everything ES CLI (es.exe).
 После триггера <найди папку :> пользователь может простыми словами описывать, как выглядит имя, включая указания вроде
 <два ноля потом нижнее подчеркивание и слово развитие>, <два слова и оба на английском>.
 Нужно превратить описание в итоговое имя и вернуть ТОЛЬКО один объект JSON одной строкой без пояснений.

 Формат JSON:
 {{
   "trigger": "найди",            // исходное триггерное слово в нормальной форме, если оно есть, иначе пустая строка
   "target_type": "folder|file|unknown",
   "name": "готовое имя файла/папки без слов типа 'папка' и 'на диске ...'",
   "drive": "буква_диска_в_нижнем_регистре_или_all" // например "d". Если не сказано, верни "all".
 }}

 Правила:
 1. Считай командой только фразы, начинающиеся с формы слова <найди/найдите/найти/найдём/найдем>.
 2. Тип:
    - <папка/каталог/директорию> - target_type = "folder";
    - <файл/документ> - target_type = "file";
    - иначе по умолчанию "folder".
 3. Имя: возьми только основное название, исправь опечатки, сохрани порядок.
    - ВСЕГДА соблюдай явные указания пользователя (язык, разделители, состав): <два/три слова>, <оба/все на английском/русском>, <нижнее подчеркивание>, <пробел>, <цифра>, <слить слова>, и т.п.
    - Не придумывай ничего сверх указаний, не исправляй формат, если он задан.
    - Примеры преобразования:
       <два ноля потом нижнее подчеркивание и слово развитие>  "00_Развитие"
       <portable soft>  "portable soft"
       <два слова и оба на английском языке: youtube видео>  "youtube video"
       <мои сайты, только английскими словами и разделенные нижним подчеркиванием>  "my_sites"
    - Удали служебные части <папку>, <на диске ...>, <слова> и т.п.
 4. Диск:
    - если сказано <везде>, <по всем дискам>, <на всех дисках> или <на диске D или C> — верни "all";
    - иначе вытащи букву после фразы <на диске х>  "d";
    - нет буквы — "all".
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
 Ввод: "найди видео везде тренировка"
 Вывод: {{"trigger":"найди","target_type":"file","name":"тренировка","drive":"all"}}

 Текст запроса: "{text}"
 """

    candidates = [
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
    ]
    attempted = set()
    last_error = None

    for model_name in candidates:
        if model_name in attempted:
            continue
        attempted.add(model_name)
        try:
            config = _build_search_config(model_name)
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=config,
            )
            raw = (getattr(response, "text", "") or "").strip()
            log_func(f"Gemini нормализация поиска ({model_name}), ответ: {raw}")
            data = _extract_json(raw)
            if not data:
                log_func("Не удалось распарсить JSON от Gemini для поиска")
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
            short = _short_error(e)
            log_func(f"Ошибка Gemini при нормализации ({model_name}): {short}")
            if not _should_try_fallback(e, attempted, model_name, candidates):
                break

    if last_error:
        log_func(traceback.format_exc())
    return None


def _build_search_config(model_name: str) -> types.GenerateContentConfig:
    config_kwargs = {"temperature": 0.1}
    thinking_config = _build_thinking_config(model_name)
    if thinking_config:
        config_kwargs["thinking_config"] = thinking_config
    return types.GenerateContentConfig(**config_kwargs)


def _build_thinking_config(model_name: str):
    thinking_cls = getattr(types, "ThinkingConfig", None)
    if not thinking_cls:
        return None
    thinking_fields = getattr(thinking_cls, "model_fields", {}) or {}
    if model_name.startswith("gemini-3") and "thinking_level" in thinking_fields:
        return thinking_cls(thinking_level="minimal")
    if model_name.startswith("gemini-2.5") and "thinking_budget" in thinking_fields:
        return thinking_cls(thinking_budget=0)
    return None


def _short_error(error: Exception) -> str:
    """Сокращает шумные HTML/stacktrace ошибки для логов."""
    txt = str(error) if error else ""
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt[:400]


def _should_try_fallback(
    error: Exception, attempted: set, current_model: str, candidates: list
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


def _extract_json(text: str) -> Optional[dict]:
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
