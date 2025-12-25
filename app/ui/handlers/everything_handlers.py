# -*- coding: utf-8 -*-
"""Обработчики Everything."""

import os

from app.core.app_config import COLORS, EXE_DIR


def on_everything_dir_changed(window) -> None:
    internal_dir = os.path.normpath(os.path.join(EXE_DIR, "_internal", "Everything"))
    if hasattr(window, "everything_dir_edit"):
        window.everything_dir_edit.setText(internal_dir)
    if window.assistant.settings.get("everything_dir"):
        window.assistant.save_setting("everything_dir", "")
    refresh_everything_status(window, startup_check=False)
    window.assistant.show_status(
        "Папка Everything фиксирована: _internal/Everything",
        COLORS["accent"],
        False,
    )


def on_everything_browse(window) -> None:
    window.assistant.show_status("Выбор папки отключен", COLORS["btn_warning"], False)


def on_everything_clear(window) -> None:
    on_everything_dir_changed(window)


def on_everything_check(window) -> None:
    refresh_everything_status(window, startup_check=True)


def refresh_everything_status(window, startup_check: bool = False) -> None:
    window.assistant.update_everything_paths(None)

    es_path = window.assistant.search_handler.es_path
    everything_path = window.assistant.search_handler.everything_path

    es_ok = bool(es_path and os.path.exists(es_path))
    exe_ok = bool(everything_path and os.path.exists(everything_path))

    def _pretty_path(value: str) -> str:
        return os.path.normpath(value) if value else value

    if startup_check:
        ready = window.assistant.search_handler.ensure_everything_running(
            timeout_s=10.0, force_start=True
        )
    else:
        ready = window.assistant.search_handler.is_everything_ready()

    running = window.assistant.search_handler.is_everything_process_running()
    if ready:
        status_text = "готов"
    elif running:
        status_text = "запущен, IPC не готов"
    else:
        status_text = "не готов"
    es_text = _pretty_path(es_path) if es_ok else "не найден"
    exe_text = _pretty_path(everything_path) if exe_ok else "не найден"
    instance_name = window.assistant.search_handler.instance_name
    instance_text = instance_name or "по умолчанию"

    error_text = ""
    last_error = window.assistant.search_handler.last_es_error
    if not ready and last_error:
        error_text = "\nОшибка: " + last_error

    window.everything_status_label.setText(
        "Статус: "
        + status_text
        + "\nes.exe: "
        + es_text
        + "\nEverything.exe: "
        + exe_text
        + "\nЭкземпляр: "
        + instance_text
        + error_text
    )


def on_request_refresh_everything(window) -> None:
    if hasattr(window, "everything_status_label"):
        refresh_everything_status(window, startup_check=False)
