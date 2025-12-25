# -*- coding: utf-8 -*-
"""
Предзагрузка ONNXRuntime и настройка DLL-пути.
Нужна для стабильной работы VAD при разных порядках импорта.
"""

import ctypes
import importlib.util
import os
import sys
from typing import Optional

_DLL_DIR_HANDLES = []
_DLL_DIR_PATHS = set()
_PRELOAD_RESULT = None
_PRELOAD_ERROR = None
_PRELOAD_CAPI_DIR = None
_PRELOAD_USED_KMP = False
_PRELOAD_DLLS = []
_PRELOAD_DLL_ERRORS = []
_PREPARE_INFO = {}


def _normalize_path(value: str) -> str:
    return os.path.normcase(os.path.abspath(value))


def _path_in_env(value: str) -> bool:
    if not value:
        return False
    target = _normalize_path(value)
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if entry and _normalize_path(entry) == target:
            return True
    return False


def _find_onnxruntime_dirs():
    package_dir = None
    capi_dir = None
    meipass = getattr(sys, "_MEIPASS", None)
    spec = importlib.util.find_spec("onnxruntime")
    if spec and spec.submodule_search_locations:
        package_dir = os.path.abspath(spec.submodule_search_locations[0])
        candidate = os.path.join(package_dir, "capi")
        if os.path.isdir(candidate):
            capi_dir = candidate
    if not capi_dir and meipass:
        candidate = os.path.join(meipass, "onnxruntime", "capi")
        if os.path.isdir(candidate):
            capi_dir = candidate
            package_dir = os.path.join(meipass, "onnxruntime")
    return package_dir, capi_dir, meipass


def _add_onnxruntime_dll_path() -> Optional[str]:
    global _PREPARE_INFO
    package_dir, capi_dir, meipass = _find_onnxruntime_dirs()
    path_present = False
    path_added = False
    dll_dir_added = False
    if capi_dir:
        path_present = _path_in_env(capi_dir)
        if not path_present:
            os.environ["PATH"] = capi_dir + os.pathsep + os.environ.get("PATH", "")
            path_added = True
        if hasattr(os, "add_dll_directory"):
            norm_capi = _normalize_path(capi_dir)
            if norm_capi not in _DLL_DIR_PATHS:
                try:
                    handle = os.add_dll_directory(capi_dir)
                    _DLL_DIR_HANDLES.append(handle)
                    _DLL_DIR_PATHS.add(norm_capi)
                    dll_dir_added = True
                except Exception:
                    dll_dir_added = False
            else:
                dll_dir_added = True
    _PREPARE_INFO = {
        "package_dir": package_dir,
        "capi_dir": capi_dir,
        "meipass": meipass,
        "path_present": path_present,
        "path_added": path_added,
        "dll_directory_added": dll_dir_added,
        "kmp_duplicate_lib_ok": os.environ.get("KMP_DUPLICATE_LIB_OK"),
    }
    return capi_dir


def _preload_onnxruntime_dlls(capi_dir: Optional[str]):
    loaded = []
    errors = []
    if os.name != "nt" or not capi_dir:
        return loaded, errors
    for name in ("onnxruntime.dll", "onnxruntime_providers_shared.dll"):
        dll_path = os.path.join(capi_dir, name)
        if not os.path.isfile(dll_path):
            continue
        try:
            ctypes.WinDLL(dll_path)
            loaded.append(dll_path)
        except Exception as e:
            errors.append((dll_path, str(e)))
    return loaded, errors


def prepare_onnxruntime(log_func=None) -> Optional[str]:
    capi_dir = _add_onnxruntime_dll_path()
    if log_func:
        if capi_dir:
            log_func(f"ONNXRuntime DLL-путь подготовлен: {capi_dir}")
        else:
            log_func("ONNXRuntime DLL-путь не найден.")
    return capi_dir


def preload_onnxruntime(log_func=None, force: bool = False) -> bool:
    global _PRELOAD_RESULT, _PRELOAD_ERROR, _PRELOAD_CAPI_DIR, _PRELOAD_USED_KMP
    global _PRELOAD_DLLS, _PRELOAD_DLL_ERRORS
    if _PRELOAD_RESULT is True:
        return True
    if _PRELOAD_RESULT is not None and not force:
        return _PRELOAD_RESULT
    _PRELOAD_RESULT = None
    _PRELOAD_ERROR = None
    _PRELOAD_CAPI_DIR = _add_onnxruntime_dll_path()
    _PRELOAD_DLLS, _PRELOAD_DLL_ERRORS = _preload_onnxruntime_dlls(
        _PRELOAD_CAPI_DIR
    )
    if os.environ.get("KMP_DUPLICATE_LIB_OK", "").strip().upper() == "TRUE":
        _PRELOAD_USED_KMP = True
    for attempt in range(2):
        try:
            import onnxruntime as ort  # noqa: F401

            _PRELOAD_RESULT = True
            _PRELOAD_ERROR = None
            if log_func:
                msg = f"ONNXRuntime предварительно загружен (версия {ort.__version__})."
                if _PRELOAD_CAPI_DIR:
                    msg += f" DLL-путь: {_PRELOAD_CAPI_DIR}"
                if _PRELOAD_USED_KMP:
                    msg += " Использован KMP_DUPLICATE_LIB_OK=TRUE."
                log_func(msg)
            return _PRELOAD_RESULT
        except Exception as e:
            if attempt == 0 and os.name == "nt" and not os.environ.get(
                "KMP_DUPLICATE_LIB_OK"
            ):
                os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
                _PRELOAD_USED_KMP = True
                continue
            _PRELOAD_RESULT = False
            _PRELOAD_ERROR = e
            if log_func:
                log_func(
                    "ONNXRuntime предварительно не загрузился. "
                    f"Причина: {e}"
                )
            return _PRELOAD_RESULT
    return _PRELOAD_RESULT


def ensure_onnxruntime_dll_path() -> Optional[str]:
    return _add_onnxruntime_dll_path()


def get_prepare_info():
    return dict(_PREPARE_INFO)


def get_preload_error():
    return _PRELOAD_ERROR


def was_kmp_workaround_used() -> bool:
    return _PRELOAD_USED_KMP


def get_preload_dll_errors():
    return list(_PRELOAD_DLL_ERRORS)
