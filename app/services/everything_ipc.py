# -*- coding: utf-8 -*-
"""Проверка готовности IPC и связки es.exe."""

import os
import subprocess
import time
from typing import Optional, Tuple


def is_everything_ready(runtime) -> bool:
    return _probe_es_ready(runtime)


def _probe_es_ready(runtime) -> bool:
    ready, error = _probe_es_ready_for_instance(runtime, runtime.instance_name)
    runtime.last_es_error = error
    return ready


def _probe_es_ready_for_instance(
    runtime, instance_name: Optional[str]
) -> Tuple[bool, str]:
    if not runtime.es_path or not os.path.exists(runtime.es_path):
        return False, "es.exe не найден"
    try:
        args = [runtime.es_path]
        if instance_name:
            args += ["-instance", instance_name]
        result = subprocess.run(
            args + ["-n", "1", "*"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=2,
        )
        output = (result.stdout or "") + "\n" + (result.stderr or "")
        lowered = output.lower()
        if "ipc" in lowered and "not running" in lowered:
            return False, "IPC: сервер не запущен"
        if "ipc" in lowered and "server" in lowered and "not" in lowered:
            return False, "IPC: сервер недоступен"
        if "ipc" in lowered and "failed" in lowered:
            return False, "IPC: ошибка подключения"
        if result.returncode == 0:
            return True, ""
        if (result.stdout or "").strip():
            return True, ""
        lines = [line.strip() for line in output.splitlines() if line.strip()]
        if lines:
            return False, lines[0]
        return False, f"код {result.returncode}"
    except Exception:
        return False, "не удалось выполнить es.exe"


def _wait_for_es_ready(runtime, timeout_s: float) -> bool:
    deadline = time.monotonic() + max(0.0, timeout_s)
    while time.monotonic() < deadline:
        if _probe_es_ready(runtime):
            return True
        time.sleep(0.2)
    if runtime.last_es_error:
        runtime.log(
            "es.exe не смог подключиться к Everything вовремя: "
            f"{runtime.last_es_error}"
        )
    else:
        runtime.log("es.exe не смог подключиться к Everything вовремя.")
    return False


def _find_ready_running_instance(runtime) -> Optional[Optional[str]]:
    candidates = runtime._get_running_instance_candidates()
    if not candidates:
        candidates = [None]
    last_error = ""
    for instance_name in candidates:
        ready, error = _probe_es_ready_for_instance(runtime, instance_name)
        if ready:
            return instance_name
        if error:
            last_error = error
    if last_error:
        runtime.last_es_error = last_error
    return None


def _log_ipc_hint(runtime) -> None:
    if not runtime.last_es_error:
        return
    lowered = runtime.last_es_error.lower()
    if "unable to send ipc message" in lowered:
        runtime.log(
            "Подсказка: Everything может быть запущен от администратора. "
            "Снимите 'Run as administrator' и перезапустите Everything."
        )
    if "ipc" in lowered and "window not found" in lowered:
        runtime.log(
            "Подсказка: Everything может быть не запущен, запущен от администратора "
            "или запущен как сервис без интерфейса. Снимите 'Run as administrator' "
            "и запустите Everything обычным способом."
        )
