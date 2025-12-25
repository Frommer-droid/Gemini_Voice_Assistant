# -*- coding: utf-8 -*-
"""Состояние и пути Everything Runtime."""

import os
from typing import Callable, Optional

from app.services.everything_paths import (
    ES_EXE_PATH,
    EVERYTHING_EXE_PATH,
    format_path_for_log,
    get_app_base_dir,
    is_internal_everything_path,
    normalize_base_dir,
    normalize_path,
    resolve_es_exe_path,
    resolve_everything_exe_path,
)

_UNSET = object()


def init_runtime(
    runtime,
    log_func: Callable[[str], None],
    es_path: str = ES_EXE_PATH,
    everything_path: str = EVERYTHING_EXE_PATH,
) -> None:
    runtime.log = log_func
    runtime.es_path = es_path
    runtime.everything_path = everything_path
    runtime.last_es_error = ""
    runtime.instance_name = None
    runtime.default_instance_name = "gemini_voice_assistant"
    runtime.previous_instance_name = None
    runtime._last_start_mode = ""
    runtime._internal_default_logged = False
    runtime._internal_missing_logged = False
    runtime._fallback_default_logged = False
    runtime._base_dir = None
    runtime._started_instances = []
    runtime._cmdline_source = None
    runtime._cmdline_count = None
    runtime._autostart_block_until = 0.0
    runtime._autostart_block_reason = ""
    runtime._autostart_block_logged = False


def update_paths(runtime, base_dir: Optional[str] = None) -> None:
    runtime._base_dir = normalize_base_dir(base_dir)
    internal_dir = normalize_base_dir(
        os.path.join(get_app_base_dir(), "_internal", "Everything")
    )
    internal_es = resolve_es_exe_path(internal_dir, internal_only=True)
    internal_exe = resolve_everything_exe_path(internal_dir, internal_only=True)
    if internal_es and internal_exe:
        runtime.es_path = internal_es
        runtime.everything_path = internal_exe
        if not runtime._internal_default_logged:
            runtime.log("Использую _internal/Everything (фиксировано).")
            runtime._internal_default_logged = True
        runtime._internal_missing_logged = False
        runtime._fallback_default_logged = False
        return
    else:
        runtime._internal_default_logged = False
        if not runtime._internal_missing_logged:
            runtime.log(
                "Папка _internal/Everything не найдена. Пробую использовать Everything из корня проекта."
            )
            runtime._internal_missing_logged = True

    fallback_base = runtime._base_dir or get_app_base_dir()
    es_path = resolve_es_exe_path(fallback_base, internal_only=False)
    everything_path = resolve_everything_exe_path(fallback_base, internal_only=False)
    if not es_path or not os.path.exists(es_path):
        es_path = ""
    if not everything_path or not os.path.exists(everything_path):
        everything_path = ""
    runtime.es_path = es_path
    runtime.everything_path = everything_path
    if runtime.es_path and runtime.everything_path:
        if not runtime._fallback_default_logged:
            base_label = format_path_for_log(os.path.dirname(runtime.es_path))
            runtime.log(f"Использую Everything из папки: {base_label}")
            runtime._fallback_default_logged = True
    else:
        runtime._fallback_default_logged = False


def normalize_path_value(runtime, path: Optional[str]) -> Optional[str]:
    return normalize_path(path)


def is_internal_everything_path_value(runtime, path: Optional[str]) -> bool:
    return is_internal_everything_path(path)
