# -*- coding: utf-8 -*-
"""Оркестратор работы Everything."""

from app.services import (
    everything_instances,
    everything_ipc,
    everything_process,
    everything_state,
)
from app.services.everything_paths import ES_EXE_PATH, EVERYTHING_EXE_PATH


class EverythingRuntime:
    def __init__(
        self,
        log_func,
        es_path: str = ES_EXE_PATH,
        everything_path: str = EVERYTHING_EXE_PATH,
    ):
        everything_state.init_runtime(self, log_func, es_path, everything_path)

    update_paths = everything_state.update_paths
    _normalize_path = everything_state.normalize_path_value
    _is_internal_everything_path = everything_state.is_internal_everything_path_value

    ensure_everything_running = everything_process.ensure_everything_running
    _start_everything = everything_process._start_everything
    _start_everything_ui = everything_process._start_everything_ui
    _make_startupinfo = everything_process._make_startupinfo
    _try_start_everything_service = everything_process._try_start_everything_service
    _mark_started_instance = everything_process._mark_started_instance
    mark_started_instance = everything_process.mark_started_instance
    shutdown_started_instances = everything_process.shutdown_started_instances
    shutdown_assistant_instance = everything_process.shutdown_assistant_instance
    block_autostart = everything_process.block_autostart
    _is_autostart_blocked = everything_process._is_autostart_blocked
    _try_stop_existing_instances = everything_process._try_stop_existing_instances
    _try_stop_detected_instances = everything_process._try_stop_detected_instances
    _stop_conflicting_instances = everything_process._stop_conflicting_instances
    _stop_everything_instance = everything_process._stop_everything_instance
    _wait_for_everything = everything_process._wait_for_everything

    is_everything_running = everything_instances.is_everything_running
    is_everything_process_running = everything_instances.is_everything_process_running
    _is_everything_running = everything_instances._is_everything_running
    _is_instance_running = everything_instances._is_instance_running
    _is_process_running = everything_instances._is_process_running
    _get_running_instance_infos = everything_instances._get_running_instance_infos
    _get_running_instance_candidates = (
        everything_instances._get_running_instance_candidates
    )
    _get_everything_command_lines = everything_instances._get_everything_command_lines
    _is_service_cmdline = everything_instances._is_service_cmdline
    _is_service_running = everything_instances._is_service_running
    _extract_instance_from_cmdline = everything_instances._extract_instance_from_cmdline
    _extract_exe_path_from_cmdline = everything_instances._extract_exe_path_from_cmdline
    _is_started_instance_running = everything_instances._is_started_instance_running
    _is_desired_instance_info = everything_instances._is_desired_instance_info

    is_everything_ready = everything_ipc.is_everything_ready
    _probe_es_ready = everything_ipc._probe_es_ready
    _probe_es_ready_for_instance = everything_ipc._probe_es_ready_for_instance
    _wait_for_es_ready = everything_ipc._wait_for_es_ready
    _find_ready_running_instance = everything_ipc._find_ready_running_instance
    _log_ipc_hint = everything_ipc._log_ipc_hint
