# -*- coding: utf-8 -*-
"""Подключение сигналов и обработчиков окна."""


def connect_window_signals(window) -> None:
    window.toggle_settings_button.clicked.connect(window.toggle_settings_panel)
    window.hide_to_tray_button.clicked.connect(window.hide)
    window.assistant.ui_signals.status_changed.connect(window.update_status)
    window.assistant.ui_signals.volume_changed.connect(window.update_volume)
    window.assistant.ui_signals.recording_state_changed.connect(
        window.on_recording_state_changed
    )
    window.assistant.ui_signals.history_updated.connect(window.update_history_combo)
    window.assistant.ui_signals.request_show_window.connect(window.show_window)
    window.assistant.ui_signals.request_hide_window.connect(window.hide)
    window.assistant.ui_signals.request_show_logs.connect(window.open_log_viewer)
    window.assistant.ui_signals.request_refresh_everything.connect(
        window.on_request_refresh_everything
    )
    if hasattr(window, "tabs"):
        window.tabs.currentChanged.connect(window._schedule_expanded_autofit)

    window.whisper_combo.currentTextChanged.connect(window.on_model_changed)
    window.proxy_check.stateChanged.connect(window.on_proxy_changed)
    window.proxy_addr_edit.editingFinished.connect(window.on_proxy_addr_changed)
    window.proxy_port_edit.editingFinished.connect(window.on_proxy_port_changed)

    window.win_shift_normal.toggled.connect(window.on_win_shift_mode_changed)
    window.win_shift_continuous.toggled.connect(window.on_win_shift_mode_changed)
    window.hold_win_shift.toggled.connect(
        lambda checked: checked and window.on_hold_hotkey_changed("win+shift")
    )
    window.hold_ctrl_shift.toggled.connect(
        lambda checked: checked and window.on_hold_hotkey_changed("ctrl+shift")
    )
    window.f1_normal.toggled.connect(window.on_f1_mode_changed)
    window.f1_continuous.toggled.connect(window.on_f1_mode_changed)

    window.mic_combo.currentIndexChanged.connect(window.on_mic_changed)
    window.sound_combo.currentTextChanged.connect(window.on_sound_scheme_changed)
    window.quality_check.stateChanged.connect(window.on_quality_check_changed)
    window.min_level_spin.valueChanged.connect(window.on_min_level_changed)
    window.silence_duration_spin.valueChanged.connect(
        window.on_silence_duration_changed
    )
    window.vad_check.stateChanged.connect(window.on_vad_changed)
    window.no_speech_spin.valueChanged.connect(window.on_no_speech_changed)
    window.logprob_spin.valueChanged.connect(window.on_logprob_changed)
    window.condition_check.stateChanged.connect(window.on_condition_prev_changed)

    window.autostart_check.stateChanged.connect(window.on_autostart_changed)
    window.start_minimized_check.stateChanged.connect(
        window.on_start_minimized_changed
    )
    if hasattr(window, "first_run_btn"):
        window.first_run_btn.clicked.connect(window.open_first_run_wizard)

    window.compact_width_spin.valueChanged.connect(
        lambda v: window.on_size_setting_changed("compact_width", v)
    )
    window.compact_height_spin.valueChanged.connect(
        lambda v: window.on_size_setting_changed("compact_height", v)
    )
    window.expanded_width_spin.valueChanged.connect(
        lambda v: window.on_size_setting_changed("expanded_width", v)
    )
    window.expanded_height_spin.valueChanged.connect(
        lambda v: window.on_size_setting_changed("expanded_height", v)
    )

    window.title_font_spin.valueChanged.connect(window.apply_font_settings)
    window.status_font_spin.valueChanged.connect(window.apply_font_settings)

    window.history_width_spin.valueChanged.connect(
        lambda v: window.on_size_setting_changed("history_window_width", v)
    )
    window.history_height_spin.valueChanged.connect(
        lambda v: window.on_size_setting_changed("history_window_height", v)
    )
    window.history_font_spin.valueChanged.connect(
        lambda v: window.on_size_setting_changed("history_font_size", v)
    )

    window.log_width_spin.valueChanged.connect(
        lambda v: window.on_size_setting_changed("log_window_width", v)
    )
    window.log_height_spin.valueChanged.connect(
        lambda v: window.on_size_setting_changed("log_window_height", v)
    )
    window.log_font_spin.valueChanged.connect(
        lambda v: window.on_size_setting_changed("log_font_size", v)
    )

    window.view_logs_btn.clicked.connect(window.open_log_viewer)
    window.clear_logs_btn.clicked.connect(window.clear_logs)
    window.view_history_btn.clicked.connect(window.show_selected_history)
    window.open_history_file_btn.clicked.connect(window.open_history_file)
    window.clear_history_btn.clicked.connect(window.clear_history)
    window.gemini_prompt_edit.textChanged.connect(
        window.on_gemini_prompt_text_changed_profile
    )
    window.gemini_splitter.splitterMoved.connect(window.on_gemini_splitter_moved)
    window.selection_word_edit.editingFinished.connect(
        window.on_selection_word_changed
    )
    window.pro_word_edit.editingFinished.connect(window.on_pro_word_changed)
    window.flash_word_edit.editingFinished.connect(window.on_flash_word_changed)
