# -*- coding: utf-8 -*-
"""Обнаружение экземпляров Everything и разбор командных строк."""

import os
import re
import subprocess
from typing import List, Optional


def is_everything_running(runtime) -> bool:
    if runtime.instance_name:
        return _is_instance_running(runtime, runtime.instance_name)
    return _is_everything_running(runtime)


def is_everything_process_running(runtime) -> bool:
    """Быстрая проверка: есть ли процесс Everything (без проверки instance)."""
    return _is_everything_running(runtime)


def _is_everything_running(runtime) -> bool:
    return _is_process_running(runtime, "Everything.exe") or _is_process_running(
        runtime, "Everything64.exe"
    )


def _is_instance_running(runtime, instance_name: Optional[str]) -> bool:
    if not instance_name:
        return _is_everything_running(runtime)
    for info in _get_running_instance_infos(runtime):
        if info.get("instance") == instance_name:
            return True
    return False


def _is_process_running(runtime, exe_name: str) -> bool:
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"IMAGENAME eq {exe_name}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return exe_name.lower() in (result.stdout or "").lower()
    except Exception:
        return False


def _get_running_instance_infos(runtime) -> List[dict]:
    infos = []
    for cmdline in _get_everything_command_lines(runtime):
        instance = _extract_instance_from_cmdline(cmdline)
        exe_path = _extract_exe_path_from_cmdline(cmdline)
        infos.append({"instance": instance, "path": exe_path, "cmd": cmdline})
    return infos


def _get_running_instance_candidates(runtime) -> List[Optional[str]]:
    lines = _get_everything_command_lines(runtime)
    if not lines:
        return []

    instances: List[Optional[str]] = []
    for cmdline in lines:
        instance = _extract_instance_from_cmdline(cmdline)
        if instance:
            if instance not in instances:
                instances.append(instance)
        else:
            if None not in instances:
                instances.append(None)
    return instances


def _get_everything_command_lines(runtime) -> List[str]:
    commands = [
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process "
                "-Filter \"Name='Everything.exe' OR Name='Everything64.exe'\" "
                "| Where-Object { $_.CommandLine } "
                "| Select-Object -ExpandProperty CommandLine"
            ),
        ],
        [
            "wmic",
            "process",
            "where",
            "name='Everything.exe' or name='Everything64.exe'",
            "get",
            "CommandLine",
            "/VALUE",
        ],
    ]

    for cmd in commands:
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                timeout=3,
            )
            output = (result.stdout or "").strip()
            if not output:
                continue
            lines = [line.strip() for line in output.splitlines() if line.strip()]
            if cmd[0].lower() == "wmic":
                cmdlines = []
                for line in lines:
                    if line.lower().startswith("commandline="):
                        value = line.split("=", 1)[1].strip()
                        if value:
                            cmdlines.append(value)
                if cmdlines:
                    if (
                        runtime._cmdline_source != "wmic"
                        or runtime._cmdline_count != len(cmdlines)
                    ):
                        runtime.log(
                            "Командные строки Everything получены через WMIC: "
                            f"{len(cmdlines)} шт."
                        )
                        runtime._cmdline_source = "wmic"
                        runtime._cmdline_count = len(cmdlines)
                    return cmdlines
                continue
            if lines:
                if (
                    runtime._cmdline_source != "powershell"
                    or runtime._cmdline_count != len(lines)
                ):
                    runtime.log(
                        "Командные строки Everything получены через PowerShell: "
                        f"{len(lines)} шт."
                    )
                    runtime._cmdline_source = "powershell"
                    runtime._cmdline_count = len(lines)
                return lines
        except Exception:
            continue
    if runtime._cmdline_source is not None:
        runtime.log(
            "Командные строки Everything не получены ни через PowerShell, ни через WMIC."
        )
        runtime._cmdline_source = None
        runtime._cmdline_count = None
    return []


def _is_service_cmdline(cmdline: str) -> bool:
    if not cmdline:
        return False
    lowered = cmdline.lower()
    return bool(
        re.search(r"(?:^|\s)-(?:svc|start-service)\b", lowered)
        or re.search(r"(?:^|\s)/(?:svc)\b", lowered)
    )


def _is_service_running(runtime) -> bool:
    for cmdline in _get_everything_command_lines(runtime):
        if _is_service_cmdline(cmdline):
            return True
    return False


def _extract_instance_from_cmdline(cmdline: str) -> Optional[str]:
    if not cmdline:
        return None
    match = re.search(
        r"(?:^|\s)-instance\s+\"?([^\"]+?)\"?(?:\s|$)",
        cmdline,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    value = match.group(1).strip()
    return value or None


def _extract_exe_path_from_cmdline(cmdline: str) -> Optional[str]:
    if not cmdline:
        return None
    match = re.match(r'^\s*\"([^\"]+)\"|^\s*([^\s]+)', cmdline)
    if not match:
        return None
    path = match.group(1) or match.group(2)
    return os.path.normpath(path) if path else None


def _is_started_instance_running(
    runtime,
    infos: List[dict],
    instance: Optional[str],
    path: Optional[str],
) -> bool:
    desired_path = runtime._normalize_path(path) if path else None
    for info in infos:
        if info.get("instance") != instance:
            continue
        if desired_path:
            info_path = runtime._normalize_path(info.get("path"))
            if not info_path:
                continue
            if info_path != desired_path:
                continue
        return True
    return False


def _is_desired_instance_info(
    runtime,
    info: dict,
    desired_instance: Optional[str],
    desired_path: Optional[str],
) -> bool:
    instance = info.get("instance")
    if instance != desired_instance:
        return False
    info_path = runtime._normalize_path(info.get("path"))
    if desired_path and info_path and desired_path != info_path:
        return False
    return True
