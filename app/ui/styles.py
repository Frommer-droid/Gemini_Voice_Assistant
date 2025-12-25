# -*- coding: utf-8 -*-
"""Глобальные стили интерфейса."""


def build_global_stylesheet(colors) -> str:
    return f"""
        QMenu {{
            background-color: {colors['bg_dark']};
            color: {colors['white']};
            border: 1px solid {colors['accent']};
        }}
        QMenu::item:selected {{
            background-color: {colors['accent']};
            color: {colors['bg_dark']};
        }}
        #centralWidget {{
            background-color: {colors['bg_main']};
            border-radius: 12px;
        }}
        #titleLabel {{
            color: {colors['white']};
            font-weight: bold;
        }}
        #statusLabel {{
            color: {colors['accent']};
        }}
        QProgressBar {{
            border: none;
            border-radius: 4px;
            background-color: {colors['bg_dark']};
        }}
        QProgressBar::chunk {{
            background-color: {colors['accent']};
            border-radius: 4px;
        }}
        #toggleButton, #hideButton {{
            background-color: transparent;
            color: {colors['accent']};
            font-size: 12pt;
            border: none;
            border-radius: 12px;
        }}
        #toggleButton:hover, #hideButton:hover {{
            background-color: {colors['bg_dark']};
        }}
        #settingsPanel, QTabWidget, QWidget, QGroupBox {{
            color: {colors['white']};
            background-color: transparent;
            border: none;
        }}
        QGroupBox {{
            border: 1px solid {colors['border_grey']};
            border-radius: 6px;
            margin-top: 8px;
            padding: 10px;
        }}
        QGroupBox::title {{
            subcontrol-origin: margin;
            subcontrol-position: top left;
            padding: 0 5px;
        }}
        QTabWidget::pane {{
            border: none;
        }}
        QTabBar::tab {{
            background: {colors['bg_dark']};
            color: {colors['white']};
            padding: 8px 12px;
            border-radius: 4px;
        }}
        QTabBar::tab:selected {{
            background: {colors['accent']};
            color: {colors['bg_dark']};
        }}
        QComboBox, QLineEdit, QPushButton, QSpinBox {{
            background-color: {colors['bg_dark']};
            color: {colors['white']};
            border: 1px solid {colors['accent']};
            border-radius: 4px;
            padding: 8px;
        }}
        QPushButton {{
            background-color: {colors['btn_standard']};
        }}
        QPushButton:hover {{
            background-color: #5F92E5;
        }}
        #warningButton {{
            background-color: {colors['btn_warning']};
        }}
        #warningButton:hover {{
            background-color: #d99a6c;
        }}
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 16px;
            height: 16px;
            border: 1px solid {colors['accent']};
            border-radius: 4px;
        }}
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background-color: {colors['accent']};
        }}
        QTextEdit {{
            background-color: {colors['bg_dark']};
            color: {colors['white']};
            border: 1px solid {colors['accent']};
            border-radius: 4px;
        }}
        QSizeGrip {{
            background-color: transparent;
            image: none;
        }}
    """


def apply_global_styles(app, colors) -> None:
    app.setStyleSheet(build_global_stylesheet(colors))
