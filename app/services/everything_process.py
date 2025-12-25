# -*- coding: utf-8 -*-
"""Запуск/остановка Everything и управление процессами."""

import os
import subprocess
import time
from typing import List, Optional

from app.services.everything_paths import format_path_for_log
from app.services.everything_state import _UNSET


def ensure_everything_running(
    runtime, timeout_s: float = 4.0, force_start: bool = False
) -> bool:
    has_custom_dir = bool(runtime._base_dir)
    if force_start and has_custom_dir:
        if not runtime.everything_path or not os.path.exists(runtime.everything_path):
            runtime.log("Everything не найден. Поиск будет недоступен.")
            return False
        if runtime._is_everything_running():
            runtime.log("Перезапуск Everything по запросу пользователя.")
            _stop_conflicting_instances(runtime)
            stopped = _try_stop_existing_instances(runtime)
            if not stopped:
                stopped = _try_stop_detected_instances(runtime)
            if not stopped and runtime._is_everything_running():
                runtime.last_es_error = (
                    runtime.last_es_error or "Не удалось остановить Everything"
                )
                runtime.log(
                    "Everything уже запущен, но остановить его не удалось. "
                    "Новый экземпляр не запускаю."
                )
                runtime._log_ipc_hint()
                return False
        _start_everything(runtime, mark_started=True)
        if runtime._wait_for_es_ready(timeout_s):
            return True
        runtime._log_ipc_hint()
        return False

    ready, error = runtime._probe_es_ready_for_instance(runtime.instance_name)
    runtime.last_es_error = error
    if ready:
        return True
    if _is_autostart_blocked(runtime):
        return False
    if not runtime.everything_path or not os.path.exists(runtime.everything_path):
        runtime.log("Everything не найден. Поиск будет недоступен.")
        return False
    if runtime.instance_name:
        if runtime._is_instance_running(runtime.instance_name):
            runtime.mark_started_instance(instance_name=runtime.instance_name)
            if runtime._wait_for_es_ready(timeout_s):
                return True
            runtime.log(
                "Экземпляр Everything запущен, но IPC недоступен. "
                "Пробую запустить интерфейс для экземпляра ассистента."
            )
            _start_everything_ui(
                runtime,
                log_reason="fallback",
                use_startup_flag=True,
                mark_started=True,
            )
            if runtime._wait_for_es_ready(timeout_s):
                return True
            runtime._log_ipc_hint()
            return False
        _start_everything(runtime, mark_started=True)
        if runtime._wait_for_es_ready(timeout_s):
            return True
        runtime._log_ipc_hint()
        return False

    if runtime._is_everything_running():
        if not has_custom_dir:
            found_instance = runtime._find_ready_running_instance()
            if found_instance is not None:
                if found_instance != runtime.instance_name:
                    label = found_instance or "по умолчанию"
                    runtime.log(
                        "Найден запущенный Everything, подключаюсь к экземпляру: "
                        f"{label}."
                    )
                runtime.instance_name = found_instance
                runtime.last_es_error = ""
                return True
            if runtime._is_service_running():
                runtime.log(
                    "Everything запущен как сервис без интерфейса. "
                    "Запускаю графический интерфейс для трея."
                )
            else:
                runtime.log(
                    "Everything запущен, но IPC недоступен. "
                    "Пробую запустить графический интерфейс."
                )
            _start_everything_ui(
                runtime,
                log_reason="fallback",
                use_startup_flag=True,
                mark_started=bool(runtime.instance_name),
            )
            if runtime._wait_for_es_ready(timeout_s):
                return True
            runtime._log_ipc_hint()
            return False
        if runtime.instance_name:
            runtime.log(
                "Найден запущенный Everything, но IPC недоступен. "
                "Пробую перезапустить для выбранной папки."
            )
            if _try_stop_existing_instances(runtime):
                _start_everything(runtime, mark_started=True)
                if runtime._wait_for_es_ready(timeout_s):
                    return True
            else:
                runtime.log(
                    "Не удалось остановить текущий процесс. "
                    "Пробую запустить интерфейс поверх."
                )
                _start_everything_ui(
                    runtime,
                    log_reason="fallback",
                    use_startup_flag=True,
                    mark_started=bool(runtime.instance_name),
                )
                if runtime._wait_for_es_ready(timeout_s):
                    return True
        runtime._log_ipc_hint()
        return False
    _start_everything(runtime, mark_started=True)
    if runtime._wait_for_es_ready(timeout_s):
        return True
    runtime._log_ipc_hint()
    return False


def _start_everything(runtime, mark_started: bool = True) -> bool:
    try:
        startupinfo = _make_startupinfo()
        return _start_everything_ui(
            runtime, startupinfo=startupinfo, mark_started=mark_started
        )
    except Exception as exc:
        runtime.log(f"Не удалось запустить Everything: {exc}")
        return False


def _start_everything_ui(
    runtime,
    startupinfo=None,
    log_reason: Optional[str] = None,
    use_startup_flag: bool = True,
    mark_started: bool = True,
) -> bool:
    try:
        startupinfo = startupinfo or _make_startupinfo()
        if runtime._is_internal_everything_path(runtime.everything_path):
            runtime.log("Запуск Everything из _internal/Everything.")
        args = [runtime.everything_path]
        if runtime.instance_name:
            args += ["-instance", runtime.instance_name]
        if use_startup_flag:
            args.append("-startup")
        subprocess.Popen(
            args,
            cwd=os.path.dirname(runtime.everything_path),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            startupinfo=startupinfo,
        )
        if mark_started:
            _mark_started_instance(runtime)
        reason = f", {log_reason}" if log_reason else ""
        mode = " с -startup" if use_startup_flag else ""
        path_label = format_path_for_log(runtime.everything_path) or str(
            runtime.everything_path
        )
        runtime.log(f"Запуск Everything (обычный режим{mode}{reason}): {path_label}")
        runtime._last_start_mode = "ui"
        return True
    except Exception as exc:
        runtime.log(f"Не удалось запустить Everything: {exc}")
        return False


def _make_startupinfo():
    startupinfo = None
    if hasattr(subprocess, "STARTUPINFO"):
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= getattr(subprocess, "STARTF_USESHOWWINDOW", 1)
        startupinfo.wShowWindow = 7
    return startupinfo


def _try_start_everything_service(runtime, startupinfo) -> bool:
    if not runtime.everything_path or not os.path.exists(runtime.everything_path):
        return False

    exe_path = runtime.everything_path
    exe_dir = os.path.dirname(exe_path)
    lower_path = exe_path.lower()
    is_installed = (
        "\\program files" in lower_path or "\\program files (x86)" in lower_path
    )
    modes = (
        ["-start-service", "-svc"] if is_installed else ["-svc", "-start-service"]
    )

    for mode in modes:
        if mode == "-start-service":
            try:
                result = subprocess.run(
                    [exe_path, mode],
                    cwd=exe_dir,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="ignore",
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    timeout=5,
                )
                if result.returncode == 0:
                    runtime.log("Запуск Everything service (-start-service).")
                    return True
            except Exception:
                continue
        else:
            try:
                subprocess.Popen(
                    [exe_path, mode],
                    cwd=exe_dir,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    startupinfo=startupinfo,
                )
                runtime.log("Запуск Everything service (-svc).")
                return True
            except Exception:
                continue

    return False


def _mark_started_instance(runtime) -> None:
    instance = runtime.instance_name
    path = runtime._normalize_path(runtime.everything_path)
    entry = (instance, path)
    if entry not in runtime._started_instances:
        runtime._started_instances.append(entry)


def mark_started_instance(runtime, instance_name=_UNSET, path: Optional[str] = None):
    instance = runtime.instance_name if instance_name is _UNSET else instance_name
    entry = (instance, runtime._normalize_path(path or runtime.everything_path))
    if entry not in runtime._started_instances:
        runtime._started_instances.append(entry)


def shutdown_started_instances(runtime, force_internal: bool = False) -> bool:
    if not runtime.es_path or not os.path.exists(runtime.es_path):
        return False
    if not runtime._started_instances and not force_internal:
        return False
    closed_any = False
    infos = runtime._get_running_instance_infos()
    for instance, path in list(runtime._started_instances):
        label = instance or "по умолчанию"
        path_label = format_path_for_log(path) or "неизвестный путь"
        if infos:
            if not runtime._is_started_instance_running(infos, instance, path):
                continue
            runtime.log(
                f"Закрываю Everything, запущенный ассистентом: {label} ({path_label})"
            )
            if _stop_everything_instance(runtime, instance):
                closed_any = True
            continue
        if instance:
            runtime.log(
                f"Пробую закрыть Everything по экземпляру ассистента: {label} ({path_label})"
            )
            if _stop_everything_instance(runtime, instance):
                closed_any = True
        elif path and runtime._is_internal_everything_path(path):
            runtime.log("Пробую закрыть Everything по умолчанию из _internal/Everything.")
            if _stop_everything_instance(runtime, None):
                closed_any = True

    if force_internal:
        internal_path = runtime._normalize_path(runtime.everything_path)
        if internal_path:
            matched = False
            if infos:
                for info in infos:
                    info_path = runtime._normalize_path(info.get("path"))
                    if not info_path or info_path != internal_path:
                        continue
                    matched = True
                    instance = info.get("instance")
                    label = instance or "по умолчанию"
                    path_label = format_path_for_log(info.get("path")) or "неизвестный путь"
                    runtime.log(
                        f"Закрываю Everything из _internal: {label} ({path_label})"
                    )
                    if _stop_everything_instance(runtime, instance):
                        closed_any = True
            if (
                not matched
                and not closed_any
                and runtime._is_internal_everything_path(runtime.everything_path)
                and runtime._is_everything_running()
            ):
                runtime.log(
                    "Не удалось определить путь Everything. Пробую закрыть экземпляр по умолчанию из _internal/Everything."
                )
                if _stop_everything_instance(runtime, None):
                    closed_any = True

    return closed_any


def shutdown_assistant_instance(runtime) -> bool:
    if not runtime.es_path or not os.path.exists(runtime.es_path):
        return False
    instance = runtime.instance_name or runtime.default_instance_name
    if not instance:
        return False
    runtime.log(f"Закрываю экземпляр Everything ассистента: {instance}")
    return _stop_everything_instance(runtime, instance)


def block_autostart(runtime, seconds: float, reason: str = "") -> None:
    if not seconds or seconds <= 0:
        return
    runtime._autostart_block_until = time.monotonic() + seconds
    runtime._autostart_block_reason = reason or ""
    runtime._autostart_block_logged = False


def _is_autostart_blocked(runtime) -> bool:
    if not runtime._autostart_block_until:
        return False
    if time.monotonic() >= runtime._autostart_block_until:
        runtime._autostart_block_until = 0.0
        runtime._autostart_block_reason = ""
        runtime._autostart_block_logged = False
        return False
    if not runtime._autostart_block_logged:
        reason = (
            f": {runtime._autostart_block_reason}"
            if runtime._autostart_block_reason
            else ""
        )
        runtime.log(f"Автозапуск Everything временно заблокирован{reason}.")
        runtime._autostart_block_logged = True
    return True


def _try_stop_existing_instances(runtime) -> bool:
    if not runtime.es_path or not os.path.exists(runtime.es_path):
        return False

    candidates: List[Optional[str]] = []
    if runtime.instance_name:
        candidates.append(runtime.instance_name)
    if runtime.previous_instance_name and runtime.previous_instance_name not in candidates:
        candidates.append(runtime.previous_instance_name)
    candidates.append(None)

    stopped_any = False
    for instance_name in candidates:
        if _stop_everything_instance(runtime, instance_name):
            stopped_any = True

    if stopped_any:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not runtime._is_everything_running():
                break
            time.sleep(0.2)

    return stopped_any and not runtime._is_everything_running()


def _try_stop_detected_instances(runtime) -> bool:
    candidates = runtime._get_running_instance_candidates()
    if not candidates:
        return False

    labels = [name or "по умолчанию" for name in candidates]
    runtime.log(f"Обнаружены экземпляры Everything: {', '.join(labels)}")

    stopped_any = False
    for instance_name in candidates:
        if _stop_everything_instance(runtime, instance_name):
            stopped_any = True

    if stopped_any:
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if not runtime._is_everything_running():
                break
            time.sleep(0.2)

    return stopped_any and not runtime._is_everything_running()


def _stop_conflicting_instances(runtime) -> bool:
    infos = runtime._get_running_instance_infos()
    if not infos:
        return False

    desired_instance = runtime.instance_name
    desired_path = runtime._normalize_path(runtime.everything_path)
    stopped_any = False

    for info in infos:
        if runtime._is_desired_instance_info(info, desired_instance, desired_path):
            continue
        instance_label = info.get("instance") or "по умолчанию"
        path_label = format_path_for_log(info.get("path")) or "неизвестный путь"
        runtime.log(
            f"Останавливаю лишний экземпляр Everything: {instance_label} ({path_label})"
        )
        if _stop_everything_instance(runtime, info.get("instance")):
            stopped_any = True

    return stopped_any


def _stop_everything_instance(runtime, instance_name: Optional[str]) -> bool:
    args = [runtime.es_path]
    label = "по умолчанию"
    if instance_name:
        args += ["-instance", instance_name]
        label = instance_name
    args.append("-exit")
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            timeout=4,
        )
        if result.returncode == 0:
            runtime.log(f"Остановлен экземпляр Everything: {label}")
            return True
    except Exception:
        pass
    return False


def _wait_for_everything(runtime, timeout_s: float) -> bool:
    deadline = time.monotonic() + max(0.0, timeout_s)
    while time.monotonic() < deadline:
        if runtime._is_everything_running():
            return True
        time.sleep(0.2)
    runtime.log("Everything не успел запуститься вовремя.")
    return False
