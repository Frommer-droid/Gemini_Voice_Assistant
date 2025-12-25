import locale
import os
import subprocess
import tempfile
import traceback
from typing import List, Optional

from app.services.everything_models import SearchQuery
from app.services.everything_paths import format_path_for_log


def build_es_base_args(es_path: str, instance_name: Optional[str]) -> List[str]:
    args = [es_path]
    if instance_name:
        args += ["-instance", instance_name]
    return args


def format_args_for_log(args: List[str]) -> List[str]:
    formatted: List[str] = []
    expect_path = False
    for index, arg in enumerate(args):
        if expect_path:
            formatted.append(format_path_for_log(arg))
            expect_path = False
            continue
        if index == 0:
            formatted.append(format_path_for_log(arg))
            continue
        if arg in ("-path", "-export-txt"):
            formatted.append(arg)
            expect_path = True
            continue
        formatted.append(arg)
    return formatted


def run_es_search(
    log_func,
    es_path: str,
    instance_name: Optional[str],
    pattern: Optional[str],
    query: SearchQuery,
) -> List[str]:
    """
    Запускает es.exe и читает результаты из временного файла в UTF-8 (с BOM),
    чтобы избежать проблем с кодировками stdout. Делает два запроса:
    1) regex (фаззи по правилам)
    2) прямой текстовый (для точных совпадений вроде 'Развитие' или 'Portable Soft')
    """
    base_args = build_es_base_args(es_path, instance_name)
    if query.drive:
        base_args += ["-path", f"{query.drive}:\\"]

    type_flag = (
        "/ad"
        if query.target_type == "folder"
        else "/a-d"
        if query.target_type == "file"
        else None
    )
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

    plain_args = (
        base_args
        + ([search_text] if search_text else [])
        + ["-n", "30", "-sort", "name-ascending"]
    )
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
            log_args = format_args_for_log(export_args)
            log_func(f"Выполняю поиск через es.exe ({label}): {log_args}")

            result = subprocess.run(export_args, capture_output=True, check=False)
        except Exception as e:
            log_func(f"Ошибка запуска es.exe ({label}): {e}")
            log_func(traceback.format_exc())
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
                        lines = [
                            line.strip() for line in f.readlines() if line.strip()
                        ]
                except Exception:
                    with open(tmp_path, "r", encoding="cp1251", errors="replace") as f:
                        lines = [
                            line.strip() for line in f.readlines() if line.strip()
                        ]
            except Exception as e:
                log_func(f"Не удалось прочитать экспортированный файл ({label}): {e}")
            finally:
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

        if not lines and result and result.stdout:
            for enc in (
                "utf-8",
                "cp1251",
                "cp866",
                "utf-16le",
                locale.getpreferredencoding(False) or "utf-8",
            ):
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

    log_func(f"Результаты es.exe: {len(uniq_lines)} записей")
    return uniq_lines
