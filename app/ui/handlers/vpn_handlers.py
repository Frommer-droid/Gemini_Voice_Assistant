# -*- coding: utf-8 -*-
"""Обработчики VLESS VPN."""

from PySide6.QtWidgets import QMessageBox

from app.core.app_config import COLORS
from app.utils.logging_utils import log_message


def vless_connect(window) -> None:
    if not window.vless_enabled_check.isChecked():
        window.vless_enabled_check.setChecked(True)
        window.assistant.save_setting("vless_enabled", True)

    url = window.vless_url_edit.text().strip()
    if not url:
        QMessageBox.warning(window, "Ошибка", "Введите VLESS URL")
        return

    if window.assistant.vless_manager.start(url):
        update_vpn_status(window)
        window.assistant.show_status("VLESS VPN подключен!", COLORS["accent"], False)
        window.assistant.setup_gemini()
    else:
        window.vless_status_label.setText("Статус: ? ошибка")
        window.assistant.show_status(
            "Ошибка подключения VPN", COLORS["btn_warning"], False
        )


def vless_disconnect(window) -> None:
    window.assistant.vless_manager.stop()
    update_vpn_status(window)
    window.assistant.show_status("VPN отключен", COLORS["accent"], False)
    window.assistant.setup_gemini()


def vless_test(window) -> None:
    port = window.assistant.vless_manager.local_socks_port
    if window.assistant.vless_manager.is_running and window.assistant.settings.get(
        "vless_enabled", False
    ):
        if window.assistant.vless_manager._check_socks_port():
            status_text = f"VLESS VPN работает\nПрокси: 127.0.0.1:{port}"
        else:
            status_text = (
                f"Процесс запущен, но порт 127.0.0.1:{port} недоступен.\n"
                "Перезапустите VPN или проверьте брандмауэр."
            )
        QMessageBox.information(
            window,
            "VPN активен",
            status_text,
        )
    else:
        QMessageBox.warning(
            window,
            "VPN неактивен",
            "VLESS VPN не подключен или выключен переключателем.",
        )


def on_vless_enabled_changed(window, state) -> None:
    enabled = bool(state)
    window.assistant.save_setting("vless_enabled", enabled)
    status = "включён" if enabled else "выключен"
    window.assistant.show_status(f"VLESS VPN {status}", COLORS["accent"], False)
    if not enabled and window.assistant.vless_manager.is_running:
        window.assistant.vless_manager.stop()
        update_vpn_status(window)
        window.assistant.setup_gemini()


def on_vless_url_changed(window) -> None:
    window.assistant.save_setting("vless_url", window.vless_url_edit.text())
    window.assistant.show_status("VLESS URL сохранён", COLORS["accent"], False)


def on_vless_autostart_changed(window, state) -> None:
    enabled = bool(state)
    window.assistant.save_setting("vless_autostart", enabled)
    status = "включён" if enabled else "выключен"
    window.assistant.show_status(f"Автозапуск VPN {status}", COLORS["accent"], False)


def on_vless_port_changed(window, value) -> None:
    """Обработчик изменения порта VLESS"""
    manager = window.assistant.vless_manager
    was_running = manager.is_running
    if was_running:
        manager.stop()

    window.assistant.save_setting("vless_port", value)
    manager.local_socks_port = value

    if was_running:
        url = window.assistant.settings.get("vless_url", "").strip()
        if url:
            manager.start(url)
            update_vpn_status(window)
            window.assistant.setup_gemini()

    window.assistant.show_status(
        f"Порт VLESS VPN: {value}", COLORS["accent"], False
    )
    log_message(f"Порт VLESS VPN изменён на: {value}")


def update_vpn_status(window) -> None:
    """Обновление статуса VPN в интерфейсе"""
    if not hasattr(window, "vless_status_label"):
        return

    if window.assistant.vless_manager.is_running:
        if window.assistant.vless_manager._check_socks_port():
            window.vless_status_label.setText("Статус: ✅ подключено")
            window.vless_status_label.setStyleSheet(
                "color: #3AE2CE; font-weight: bold;"
            )
        else:
            window.vless_status_label.setText(
                "Статус: ? процесс запущен, порт недоступен"
            )
            window.vless_status_label.setStyleSheet("color: #BF8255;")
    else:
        window.vless_status_label.setText("Статус: не подключено")
        window.vless_status_label.setStyleSheet("color: #626C71;")
