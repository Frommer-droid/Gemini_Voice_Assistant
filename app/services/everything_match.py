import os
import re
from difflib import SequenceMatcher
from typing import List, Optional

from app.services.everything_paths import format_path_for_log


def build_regex_pattern(name: str, target_type: str) -> Optional[str]:
    """Создаёт регэксп по правилам из ТЗ для имени файла/папки."""
    if not name:
        return None

    cleaned_name = strip_punctuation(name)
    words = _tokenize_name(cleaned_name)
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


def strip_punctuation(name: str) -> str:
    """Убирает знаки препинания, оставляя буквы/цифры/подчёркивания и дефисы."""
    cleaned = re.sub(r"[^\w\sЁё-]+", " ", name)
    return " ".join(cleaned.split())


def select_best_path(
    paths: List[str],
    target_name: str,
    drive: Optional[str] = None,
    log_func=None,
) -> Optional[str]:
    """Выбирает лучший путь: точное совпадение по имени папки + минимальная глубина + схожесть."""
    if not paths:
        return None
    if not (target_name or "").strip():
        return None

    def _log(message: str):
        if log_func:
            log_func(message)

    target_norm = _normalize_text(target_name)
    target_clean = strip_punctuation(target_name)

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
                    path_label = format_path_for_log(alias_path) or str(alias_path)
                    _log(f"Прямое совпадение по алиасу: {path_label}")
                    return alias_path

    # Приоритет: прямой путь <drive>:\<target> если существует
    if drive:
        direct_path = os.path.join(f"{drive.upper()}:\\", target_clean)
        if os.path.exists(direct_path):
            path_label = format_path_for_log(direct_path) or str(direct_path)
            _log(f"Прямое совпадение по диску: {path_label}")
            return direct_path

    def score(path: str) -> int:
        base = os.path.basename(path)
        base_norm = _normalize_text(base)
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
    path_label = format_path_for_log(best) or str(best)
    _log(f"Лучший кандидат для открытия: {path_label}")
    return best


def _normalize_text(text: str) -> str:
    txt = (text or "").lower().replace("ё", "е")
    return re.sub(r"[^а-яa-z0-9]+", "", txt)


def _tokenize_name(name: str) -> List[str]:
    """Нормализация имени: заменяем подчёркивания/дефисы и вставляем пробелы по CamelCase."""
    with_spaces = re.sub(r"[_-]+", " ", name)
    camel_split = re.sub(r"(?<=[A-Za-zА-Яа-яЁё0-9])(?=[A-ZА-Я])", " ", with_spaces)
    normalized = camel_split.lower().replace("ё", "е")
    return [w for w in normalized.split() if w]
