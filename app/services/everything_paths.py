import os
import shutil
import sys
from typing import Optional

# Путь к консольной утилите Everything ES CLI
DEFAULT_ES_EXE_PATH = r"C:\Program Files\Everything\ES-1.1.0.30.x64\es.exe"
DEFAULT_EVERYTHING_EXE_PATHS = [
    r"C:\Program Files\Everything\Everything.exe",
    r"C:\Program Files\Everything\Everything64.exe",
    r"C:\Program Files (x86)\Everything\Everything.exe",
    r"C:\Program Files (x86)\Everything\Everything64.exe",
]


def get_app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(sys.argv[0]))


def normalize_base_dir(base_dir: Optional[str]) -> Optional[str]:
    if not base_dir:
        return None
    cleaned = str(base_dir).strip().strip('"')
    if not cleaned:
        return None
    if os.path.isfile(cleaned):
        cleaned = os.path.dirname(cleaned)
    return cleaned if os.path.isdir(cleaned) else None


def format_path_for_log(path: Optional[str]) -> str:
    if not path:
        return ""
    try:
        return os.path.normpath(str(path))
    except Exception:
        return str(path)


def resolve_es_exe_path(base_dir: Optional[str] = None, internal_only: bool = False) -> str:
    base_dir = normalize_base_dir(base_dir)
    candidates = []
    if internal_only:
        if base_dir:
            candidates.append(os.path.join(base_dir, "es.exe"))
        else:
            app_dir = get_app_base_dir()
            if app_dir:
                candidates.append(
                    os.path.join(app_dir, "_internal", "Everything", "es.exe")
                )
        for path in candidates:
            if path and os.path.exists(path):
                return os.path.normpath(path)
        return ""

    if base_dir:
        candidates.append(os.path.join(base_dir, "es.exe"))
        candidates.append(os.path.join(base_dir, "Everything", "es.exe"))

    app_dir = get_app_base_dir()
    if app_dir:
        internal_dir = os.path.join(app_dir, "_internal")
        candidates.append(os.path.join(internal_dir, "Everything", "es.exe"))
        candidates.append(os.path.join(internal_dir, "es.exe"))
        candidates.append(os.path.join(app_dir, "Everything", "es.exe"))
        candidates.append(os.path.join(app_dir, "es.exe"))

    module_dir = os.path.dirname(os.path.abspath(__file__))
    if module_dir and module_dir != app_dir:
        candidates.append(os.path.join(module_dir, "Everything", "es.exe"))
        candidates.append(os.path.join(module_dir, "es.exe"))

    path_from_env = shutil.which("es.exe") or shutil.which("es")
    if path_from_env:
        candidates.append(path_from_env)

    candidates.append(DEFAULT_ES_EXE_PATH)

    for path in candidates:
        if path and os.path.exists(path):
            return os.path.normpath(path)
    return DEFAULT_ES_EXE_PATH


def resolve_everything_exe_path(
    base_dir: Optional[str] = None, internal_only: bool = False
) -> str:
    base_dir = normalize_base_dir(base_dir)
    exe_names = (
        "Everything.exe",
        "Everything64.exe",
        "everything.exe",
        "everything64.exe",
    )
    candidates = []
    if internal_only:
        if base_dir:
            for exe_name in exe_names:
                candidates.append(os.path.join(base_dir, exe_name))
        else:
            app_dir = get_app_base_dir()
            if app_dir:
                for exe_name in exe_names:
                    candidates.append(
                        os.path.join(app_dir, "_internal", "Everything", exe_name)
                    )
        for path in candidates:
            if path and os.path.exists(path):
                return os.path.normpath(path)
        return ""

    if base_dir:
        for exe_name in exe_names:
            candidates.append(os.path.join(base_dir, exe_name))
        for exe_name in exe_names:
            candidates.append(os.path.join(base_dir, "Everything", exe_name))

    app_dir = get_app_base_dir()
    if app_dir:
        for exe_name in exe_names:
            candidates.append(os.path.join(app_dir, "_internal", "Everything", exe_name))
        for exe_name in exe_names:
            candidates.append(os.path.join(app_dir, "_internal", exe_name))
        for exe_name in exe_names:
            candidates.append(os.path.join(app_dir, "Everything", exe_name))
        for exe_name in exe_names:
            candidates.append(os.path.join(app_dir, exe_name))

    module_dir = os.path.dirname(os.path.abspath(__file__))
    if module_dir and module_dir != app_dir:
        for exe_name in exe_names:
            candidates.append(os.path.join(module_dir, "Everything", exe_name))
        for exe_name in exe_names:
            candidates.append(os.path.join(module_dir, exe_name))

    for exe_name in exe_names:
        path_from_env = shutil.which(exe_name)
        if path_from_env:
            candidates.append(path_from_env)

    candidates.extend(DEFAULT_EVERYTHING_EXE_PATHS)

    for path in candidates:
        if path and os.path.exists(path):
            return os.path.normpath(path)
    return ""


def normalize_path(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return os.path.normcase(os.path.normpath(path))


def is_internal_everything_path(path: Optional[str]) -> bool:
    internal_root = normalize_path(os.path.join(get_app_base_dir(), "_internal"))
    if not internal_root or not path:
        return False
    internal_sep = internal_root + os.sep
    return normalize_path(path).startswith(internal_sep)


ES_EXE_PATH = resolve_es_exe_path()
EVERYTHING_EXE_PATH = resolve_everything_exe_path()
