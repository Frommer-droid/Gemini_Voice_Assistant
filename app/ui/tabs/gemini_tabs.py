# -*- coding: utf-8 -*-
"""Вкладки настроек Gemini."""

from PySide6.QtCore import Qt, QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QStyle,
)


def _apply_profile_button_icons(window, button_size: int) -> None:
    def _icon(name: str, fallback: QStyle.StandardPixmap) -> QStyle.StandardPixmap:
        return getattr(QStyle.StandardPixmap, name, fallback)

    add_icon = window.style().standardIcon(
        _icon("SP_FileDialogNewFolder", QStyle.StandardPixmap.SP_DialogSaveAllButton)
    )
    rename_icon = window.style().standardIcon(
        _icon(
            "SP_FileDialogDetailedView",
            QStyle.StandardPixmap.SP_DialogRetryButton,
        )
    )
    delete_icon = window.style().standardIcon(
        _icon("SP_TrashIcon", QStyle.StandardPixmap.SP_DialogAbortButton)
    )

    window.prompt_add_btn.setIcon(add_icon)
    window.prompt_add_btn.setText("")
    window.prompt_rename_btn.setIcon(rename_icon)
    window.prompt_rename_btn.setText("")
    window.prompt_delete_btn.setIcon(delete_icon)
    window.prompt_delete_btn.setText("")

    icon_size = max(12, button_size - 8)
    icon_qsize = QSize(icon_size, icon_size)
    window.prompt_add_btn.setIconSize(icon_qsize)
    window.prompt_rename_btn.setIconSize(icon_qsize)
    window.prompt_delete_btn.setIconSize(icon_qsize)


def create_gemini_tab(window) -> None:
    tab = QWidget()
    layout = QVBoxLayout(tab)

    # ====== НОВОЕ: API ключ Gemini ======
    api_group = QGroupBox("API ключ")
    api_layout = QVBoxLayout(api_group)

    api_layout.addWidget(QLabel("Gemini API Key:"))
    window.gemini_api_key_edit = QLineEdit()
    window.gemini_api_key_edit.setText(
        window.assistant.settings.get("gemini_api_key", "")
    )
    window.gemini_api_key_edit.setPlaceholderText("AIzaSy...")
    window.gemini_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
    api_layout.addWidget(window.gemini_api_key_edit)
    layout.addWidget(api_group)

    window.gemini_api_key_edit.editingFinished.connect(
        window.on_gemini_api_key_changed
    )

    main_layout = layout
    window.gemini_splitter = QSplitter(Qt.Orientation.Vertical)

    top_widget = QWidget()
    top_layout = QVBoxLayout(top_widget)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(0)
    top_widget.setSizePolicy(
        QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
    )

    info_label = QLabel(
        "Здесь можно указать инструкцию для Gemini по обработке текста."
    )
    info_label.setWordWrap(True)
    info_label.setSizePolicy(
        QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
    )
    top_layout.addWidget(info_label)

    bottom_widget = QGroupBox("Промпт для форматирования")
    bottom_layout = QVBoxLayout(bottom_widget)
    bottom_layout.setContentsMargins(5, 5, 5, 5)

    prompts = window.assistant.settings.get("gemini_prompts")
    if not isinstance(prompts, dict) or not prompts:
        current_prompt = window.assistant.settings.get("gemini_prompt", "")
        prompts = {"Default": current_prompt}
        window.assistant.save_setting("gemini_prompts", prompts)
        window.assistant.save_setting("gemini_selected_prompt", "Default")

    selected_profile = window.assistant.settings.get(
        "gemini_selected_prompt", next(iter(prompts.keys()))
    )
    if selected_profile not in prompts:
        selected_profile = next(iter(prompts.keys()))
        window.assistant.save_setting("gemini_selected_prompt", selected_profile)

    profile_bar = QHBoxLayout()
    profile_bar.addWidget(QLabel("Профиль промпта:"))
    window.gemini_prompt_combo = QComboBox()
    window.gemini_prompt_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    window.gemini_prompt_combo.setMinimumContentsLength(8)
    window.gemini_prompt_combo.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    for name in prompts.keys():
        window.gemini_prompt_combo.addItem(name)
    window.gemini_prompt_combo.setCurrentText(selected_profile)
    window.prompt_add_btn = QPushButton("+")
    window.prompt_add_btn.setToolTip("Добавить профиль")
    window.prompt_rename_btn = QPushButton("?")
    window.prompt_rename_btn.setToolTip("Переименовать профиль")
    window.prompt_delete_btn = QPushButton("??")
    window.prompt_delete_btn.setToolTip("Удалить профиль")
    button_size = window.gemini_prompt_combo.sizeHint().height()
    for btn in (
        window.prompt_add_btn,
        window.prompt_rename_btn,
        window.prompt_delete_btn,
    ):
        btn.setFixedSize(button_size, button_size)
    _apply_profile_button_icons(window, button_size)
    profile_bar.addWidget(window.gemini_prompt_combo, 1)
    profile_bar.addWidget(window.prompt_add_btn)
    profile_bar.addWidget(window.prompt_rename_btn)
    profile_bar.addWidget(window.prompt_delete_btn)
    bottom_layout.addLayout(profile_bar)

    markdown_layout = QHBoxLayout()
    window.gemini_markdown_check = QCheckBox("Markdown")
    window.gemini_markdown_check.setToolTip(
        "Разрешить Markdown-разметку в ответах"
    )
    window.gemini_markdown_check.setChecked(
        bool(window.assistant.settings.get("gemini_markdown_enabled", False))
    )
    markdown_layout.addWidget(window.gemini_markdown_check)
    markdown_layout.addStretch()
    bottom_layout.addLayout(markdown_layout)

    window.gemini_prompt_edit = QTextEdit()
    window.gemini_prompt_edit.setAcceptRichText(False)
    window.gemini_prompt_edit.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    window.gemini_prompt_edit.setPlainText(
        window.assistant.settings.get("gemini_prompt")
    )
    bottom_layout.addWidget(window.gemini_prompt_edit, 1)
    # Показываем текст выбранного профиля в редакторе.
    try:
        window.gemini_prompt_edit.blockSignals(True)
        window.gemini_prompt_edit.setPlainText(prompts.get(selected_profile, ""))
    finally:
        window.gemini_prompt_edit.blockSignals(False)

    window.gemini_splitter.addWidget(top_widget)
    window.gemini_splitter.addWidget(bottom_widget)
    window.gemini_splitter.setChildrenCollapsible(False)

    prompt_height = max(1, window.assistant.settings.get("gemini_prompt_height", 250))
    info_height = max(1, info_label.sizeHint().height())
    window.gemini_splitter.setSizes([info_height, prompt_height])
    window.gemini_splitter.setStretchFactor(0, 0)
    window.gemini_splitter.setStretchFactor(1, 1)

    main_layout.addWidget(window.gemini_splitter)
    main_layout.setStretchFactor(window.gemini_splitter, 1)
    # Подключаем обработчики управления профилями.
    window._last_prompt_profile_name = selected_profile
    window.gemini_prompt_combo.currentTextChanged.connect(
        window.on_gemini_prompt_profile_changed
    )
    window.prompt_add_btn.clicked.connect(window.on_add_gemini_prompt_profile)
    window.prompt_rename_btn.clicked.connect(window.on_rename_gemini_prompt_profile)
    window.prompt_delete_btn.clicked.connect(window.on_delete_gemini_prompt_profile)
    window.gemini_prompt_edit.textChanged.connect(
        window.on_gemini_prompt_text_changed_profile
    )
    if hasattr(window, "gemini_markdown_check"):
        window.gemini_markdown_check.stateChanged.connect(
            window.on_gemini_markdown_changed
        )

    activation_group = QGroupBox("Активационные слова")
    activation_layout = QVBoxLayout(activation_group)

    selection_layout = QHBoxLayout()
    selection_layout.addWidget(QLabel("Для выделения:"))
    window.selection_word_edit = QLineEdit()
    window.selection_word_edit.setText(
        window.assistant.settings.get("selection_word", "выделить")
    )
    selection_layout.addWidget(window.selection_word_edit)
    activation_layout.addLayout(selection_layout)

    pro_layout = QHBoxLayout()
    pro_layout.addWidget(QLabel("Для Pro модели:"))
    window.pro_word_edit = QLineEdit()
    window.pro_word_edit.setText(window.assistant.settings.get("pro_word", "про"))
    pro_layout.addWidget(window.pro_word_edit)
    activation_layout.addLayout(pro_layout)

    flash_layout = QHBoxLayout()
    flash_layout.addWidget(QLabel("Для Flash модели:"))
    window.flash_word_edit = QLineEdit()
    window.flash_word_edit.setText(window.assistant.settings.get("flash_word", "флеш"))
    flash_layout.addWidget(window.flash_word_edit)
    activation_layout.addLayout(flash_layout)

    main_layout.addWidget(activation_group)

    window.tabs.addTab(tab, "Gemini")
    window._last_prompt_profile_name = selected_profile
    window.gemini_prompt_combo.currentTextChanged.connect(
        window.on_gemini_prompt_profile_changed
    )
    window.prompt_add_btn.clicked.connect(window.on_add_gemini_prompt_profile)
    window.prompt_rename_btn.clicked.connect(window.on_rename_gemini_prompt_profile)
    window.prompt_delete_btn.clicked.connect(window.on_delete_gemini_prompt_profile)
    if hasattr(window, "gemini_markdown_check"):
        window.gemini_markdown_check.stateChanged.connect(
            window.on_gemini_markdown_changed
        )


def create_gemini_tab_v2(window) -> None:
    tab = QWidget()
    layout = QVBoxLayout(tab)

    api_group = QGroupBox("API ключ")
    api_layout = QVBoxLayout(api_group)

    api_layout.addWidget(QLabel("Gemini API Key:"))
    window.gemini_api_key_edit = QLineEdit()
    window.gemini_api_key_edit.setText(
        window.assistant.settings.get("gemini_api_key", "")
    )
    window.gemini_api_key_edit.setPlaceholderText("AIzaSy...")
    window.gemini_api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
    api_layout.addWidget(window.gemini_api_key_edit)

    show_key_layout = QHBoxLayout()
    window.show_api_key_check = QCheckBox("Показать ключ")
    window.show_api_key_check.stateChanged.connect(
        window.toggle_api_key_visibility
    )
    show_key_layout.addWidget(window.show_api_key_check)
    show_key_layout.addStretch()
    api_layout.addLayout(show_key_layout)

    layout.addWidget(api_group)

    window.gemini_api_key_edit.editingFinished.connect(
        window.on_gemini_api_key_changed
    )

    main_layout = layout
    window.gemini_splitter = QSplitter(Qt.Orientation.Vertical)

    top_widget = QWidget()
    top_layout = QVBoxLayout(top_widget)
    top_layout.setContentsMargins(0, 0, 0, 0)
    top_layout.setSpacing(0)
    top_widget.setSizePolicy(
        QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
    )

    info_label = QLabel(
        "Здесь можно указать инструкцию для Gemini по обработке текста."
    )
    info_label.setWordWrap(True)
    info_label.setSizePolicy(
        QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum
    )
    top_layout.addWidget(info_label)

    bottom_widget = QGroupBox("Промпт для форматирования")
    bottom_layout = QVBoxLayout(bottom_widget)
    bottom_layout.setContentsMargins(5, 5, 5, 5)

    prompts = window.assistant.settings.get("gemini_prompts")
    if not isinstance(prompts, dict) or not prompts:
        current_prompt = window.assistant.settings.get("gemini_prompt", "")
        prompts = {"Default": current_prompt}
        window.assistant.save_setting("gemini_prompts", prompts)
        window.assistant.save_setting("gemini_selected_prompt", "Default")

    selected_profile = window.assistant.settings.get(
        "gemini_selected_prompt", next(iter(prompts.keys()))
    )
    if selected_profile not in prompts:
        selected_profile = next(iter(prompts.keys()))
        window.assistant.save_setting("gemini_selected_prompt", selected_profile)

    profile_bar = QHBoxLayout()
    profile_bar.addWidget(QLabel("Профиль промпта:"))
    window.gemini_prompt_combo = QComboBox()
    window.gemini_prompt_combo.setSizeAdjustPolicy(
        QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
    )
    window.gemini_prompt_combo.setMinimumContentsLength(8)
    window.gemini_prompt_combo.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed
    )
    for name in prompts.keys():
        window.gemini_prompt_combo.addItem(name)
    window.gemini_prompt_combo.setCurrentText(selected_profile)
    window.prompt_add_btn = QPushButton("+")
    window.prompt_add_btn.setToolTip("Добавить профиль")
    window.prompt_rename_btn = QPushButton("?")
    window.prompt_rename_btn.setToolTip("Переименовать профиль")
    window.prompt_delete_btn = QPushButton("??")
    window.prompt_delete_btn.setToolTip("Удалить профиль")
    button_size = window.gemini_prompt_combo.sizeHint().height()
    for btn in (
        window.prompt_add_btn,
        window.prompt_rename_btn,
        window.prompt_delete_btn,
    ):
        btn.setFixedSize(button_size, button_size)
    _apply_profile_button_icons(window, button_size)
    profile_bar.addWidget(window.gemini_prompt_combo, 1)
    profile_bar.addWidget(window.prompt_add_btn)
    profile_bar.addWidget(window.prompt_rename_btn)
    profile_bar.addWidget(window.prompt_delete_btn)
    bottom_layout.addLayout(profile_bar)

    markdown_layout = QHBoxLayout()
    window.gemini_markdown_check = QCheckBox("Markdown")
    window.gemini_markdown_check.setToolTip(
        "Разрешить Markdown-разметку в ответах"
    )
    window.gemini_markdown_check.setChecked(
        bool(window.assistant.settings.get("gemini_markdown_enabled", False))
    )
    markdown_layout.addWidget(window.gemini_markdown_check)
    markdown_layout.addStretch()
    bottom_layout.addLayout(markdown_layout)

    window.gemini_prompt_edit = QTextEdit()
    window.gemini_prompt_edit.setAcceptRichText(False)
    window.gemini_prompt_edit.setSizePolicy(
        QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
    )
    window.gemini_prompt_edit.setPlainText(prompts.get(selected_profile, ""))
    bottom_layout.addWidget(window.gemini_prompt_edit, 1)

    window.gemini_splitter.addWidget(top_widget)
    window.gemini_splitter.addWidget(bottom_widget)
    window.gemini_splitter.setChildrenCollapsible(False)

    prompt_height = max(1, window.assistant.settings.get("gemini_prompt_height", 250))
    info_height = max(1, info_label.sizeHint().height())
    window.gemini_splitter.setSizes([info_height, prompt_height])
    window.gemini_splitter.setStretchFactor(0, 0)
    window.gemini_splitter.setStretchFactor(1, 1)

    main_layout.addWidget(window.gemini_splitter)
    main_layout.setStretchFactor(window.gemini_splitter, 1)

    activation_group = QGroupBox("Ключевые слова")
    activation_layout = QVBoxLayout(activation_group)

    selection_layout = QHBoxLayout()
    selection_layout.addWidget(QLabel("Слово выделения:"))
    window.selection_word_edit = QLineEdit()
    window.selection_word_edit.setText(
        window.assistant.settings.get("selection_word", "выделить")
    )
    selection_layout.addWidget(window.selection_word_edit)
    activation_layout.addLayout(selection_layout)

    pro_layout = QHBoxLayout()
    pro_layout.addWidget(QLabel("Слово Pro-режима:"))
    window.pro_word_edit = QLineEdit()
    window.pro_word_edit.setText(window.assistant.settings.get("pro_word", "про"))
    pro_layout.addWidget(window.pro_word_edit)
    activation_layout.addLayout(pro_layout)

    flash_layout = QHBoxLayout()
    flash_layout.addWidget(QLabel("Слово Flash-режима:"))
    window.flash_word_edit = QLineEdit()
    window.flash_word_edit.setText(window.assistant.settings.get("flash_word", "флеш"))
    flash_layout.addWidget(window.flash_word_edit)
    activation_layout.addLayout(flash_layout)

    main_layout.addWidget(activation_group)

    window.tabs.addTab(tab, "Gemini")
    window._last_prompt_profile_name = selected_profile
    window.gemini_prompt_combo.currentTextChanged.connect(
        window.on_gemini_prompt_profile_changed
    )
    window.prompt_add_btn.clicked.connect(window.on_add_gemini_prompt_profile)
    window.prompt_rename_btn.clicked.connect(window.on_rename_gemini_prompt_profile)
    window.prompt_delete_btn.clicked.connect(window.on_delete_gemini_prompt_profile)
    if hasattr(window, "gemini_markdown_check"):
        window.gemini_markdown_check.stateChanged.connect(
            window.on_gemini_markdown_changed
        )
