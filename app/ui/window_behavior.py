# -*- coding: utf-8 -*-
"""Поведение окна: перетаскивание, ресайз и автоподгонка размеров."""

from PySide6.QtCore import QEvent, QPoint, QRect, Qt, QTimer
from PySide6.QtWidgets import QStyle

from app.ui.window_snap import snap_to_screen
from app.utils.logging_utils import log_message


def handle_mouse_press(window, event) -> bool:
    if event.button() == Qt.MouseButton.LeftButton:
        if hasattr(window, "size_grip"):
            grip_rect = window.size_grip.geometry()
            if grip_rect.contains(event.position().toPoint()):
                window.is_resizing = True
                return True

        edges = detect_resize_edges(window, event.position().toPoint())
        if edges:
            window.is_resizing = True
            window.resize_edges = edges
            window.resize_origin = event.globalPosition().toPoint()
            window.initial_geometry = window.geometry()
            window.setCursor(cursor_for_edges(edges))
            event.accept()
            return True

        window.resize_edges = tuple()
        window.drag_pos = (
            event.globalPosition().toPoint() - window.frameGeometry().topLeft()
        )
        event.accept()
        return True
    return False


def handle_mouse_move(window, event) -> None:
    if window.is_resizing and window.resize_edges:
        resize_from_edge(window, event.globalPosition().toPoint())
        event.accept()
        return

    if window.is_resizing:
        event.accept()
        return

    if event.buttons() == Qt.MouseButton.LeftButton:
        window.move(event.globalPosition().toPoint() - window.drag_pos)
        event.accept()
        return

    update_hover_cursor(window, event.position().toPoint())


def handle_mouse_release(window, event) -> None:
    window.is_resizing = False
    window.resize_edges = tuple()
    window.resize_origin = QPoint()
    window.initial_geometry = QRect()
    update_hover_cursor(window, event.position().toPoint())
    snap_to_screen(window)


def handle_event_filter(window, obj, event) -> bool:
    if (
        obj is getattr(window, "toggle_settings_button", None)
        and event.type() == QEvent.Type.MouseButtonPress
    ):
        if event.button() == Qt.MouseButton.RightButton:
            window.assistant.cancel_all_operations(
                "правый клик по кнопке разворачивания"
            )
            event.accept()
            return True
    return False


def detect_resize_edges(window, pos: QPoint):
    margin = getattr(window, "resize_margin", 12)
    edges = []
    if pos.x() <= margin:
        edges.append("left")
    if pos.x() >= window.width() - margin:
        edges.append("right")
    if pos.y() >= window.height() - margin:
        edges.append("bottom")
    return tuple(edges)


def cursor_for_edges(edges):
    if not edges:
        return Qt.CursorShape.ArrowCursor

    has_left = "left" in edges
    has_right = "right" in edges
    has_bottom = "bottom" in edges

    if has_bottom and has_left:
        return Qt.CursorShape.SizeBDiagCursor
    if has_bottom and has_right:
        return Qt.CursorShape.SizeFDiagCursor
    if has_bottom:
        return Qt.CursorShape.SizeVerCursor
    if has_left or has_right:
        return Qt.CursorShape.SizeHorCursor
    return Qt.CursorShape.ArrowCursor


def update_hover_cursor(window, pos: QPoint) -> None:
    if window.is_resizing:
        return
    edges = detect_resize_edges(window, pos)
    cursor = cursor_for_edges(edges)
    if cursor == Qt.CursorShape.ArrowCursor:
        window.unsetCursor()
    else:
        window.setCursor(cursor)


def resize_from_edge(window, global_pos: QPoint) -> None:
    if not window.resize_edges:
        return

    edges = set(window.resize_edges)
    delta = global_pos - window.resize_origin
    base_geom = QRect(window.initial_geometry)
    new_geom = QRect(base_geom)

    min_width = window.minimumWidth()
    min_height = window.minimumHeight()

    if "right" in edges:
        new_width = max(min_width, base_geom.width() + delta.x())
        new_geom.setWidth(new_width)

    if "left" in edges:
        new_width = base_geom.width() - delta.x()
        if new_width < min_width:
            new_left = base_geom.x() + (base_geom.width() - min_width)
            new_width = min_width
        else:
            new_left = base_geom.x() + delta.x()
        new_geom.setX(new_left)
        new_geom.setWidth(new_width)

    if "bottom" in edges:
        new_height = max(min_height, base_geom.height() + delta.y())
        new_geom.setHeight(new_height)

    window.setGeometry(new_geom)


def handle_move_event(window) -> None:
    if window.isVisible() and not window.isMinimized() and hasattr(window, "assistant"):
        pos = window.pos()
        window.assistant.save_setting("window_pos_x", pos.x())
        window.assistant.save_setting("window_pos_y", pos.y())


def handle_resize_event(window) -> None:
    if hasattr(window, "size_grip"):
        grip_size = window.size_grip.sizeHint()
        window.size_grip.move(
            window.width() - grip_size.width(), window.height() - grip_size.height()
        )

    if (
        not window.is_programmatic_resize
        and not window.isMaximized()
        and not window.isMinimized()
        and window.isVisible()
    ):
        if window.settings_expanded:
            window.assistant.save_setting("expanded_width", window.width())
            window.assistant.save_setting("expanded_height", window.height())
            if hasattr(window, "expanded_width_spin"):
                window.expanded_width_spin.blockSignals(True)
                window.expanded_width_spin.setValue(window.width())
                window.expanded_width_spin.blockSignals(False)
            if hasattr(window, "expanded_height_spin"):
                window.expanded_height_spin.blockSignals(True)
                window.expanded_height_spin.setValue(window.height())
                window.expanded_height_spin.blockSignals(False)
        else:
            window.assistant.save_setting("compact_width", window.width())
            window.assistant.save_setting("compact_height", window.height())
            if hasattr(window, "compact_width_spin"):
                window.compact_width_spin.blockSignals(True)
                window.compact_width_spin.setValue(window.width())
                window.compact_width_spin.blockSignals(False)
            if hasattr(window, "compact_height_spin"):
                window.compact_height_spin.blockSignals(True)
                window.compact_height_spin.setValue(window.height())
                window.compact_height_spin.blockSignals(False)


def layout_margins_width(layout) -> int:
    if not layout:
        return 0
    margins = layout.contentsMargins()
    return margins.left() + margins.right()


def layout_margins_height(layout) -> int:
    if not layout:
        return 0
    margins = layout.contentsMargins()
    return margins.top() + margins.bottom()


def available_screen_width(window):
    screen = window.screen()
    if not screen:
        return None
    return screen.availableGeometry().width()


def available_screen_height(window):
    screen = window.screen()
    if not screen:
        return None
    return screen.availableGeometry().height()


def calculate_compact_min_width(window) -> int:
    if not hasattr(window, "top_bar_layout"):
        return window.minimumWidth()
    label_width = window.title_label.sizeHint().width()
    left_width = window.hide_to_tray_button.sizeHint().width()
    right_width = window.toggle_settings_button.sizeHint().width()
    spacing = window.top_bar_layout.spacing()
    margins = layout_margins_width(window.main_layout)
    return left_width + right_width + label_width + spacing * 2 + margins


def calculate_expanded_min_width(window) -> int:
    compact_min = calculate_compact_min_width(window)
    tab_width = 0
    if hasattr(window, "tabs"):
        tab_bar = window.tabs.tabBar()
        tab_width = tab_bar.sizeHint().width()
        tab_margins = window.tabs.contentsMargins()
        frame = window.tabs.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        tab_width += tab_margins.left() + tab_margins.right() + frame * 2
    layout_margins = layout_margins_width(window.settings_panel.layout())
    main_margins = layout_margins_width(window.main_layout)
    return max(compact_min, tab_width + layout_margins + main_margins)


def calculate_base_min_height(window) -> int:
    if not hasattr(window, "main_layout"):
        return window.minimumHeight()
    top_height = max(
        window.hide_to_tray_button.sizeHint().height(),
        window.title_label.sizeHint().height(),
        window.toggle_settings_button.sizeHint().height(),
    )
    status_height = window.status_label.sizeHint().height()
    bottom_height = window.bottom_bar.sizeHint().height()
    spacing = window.main_layout.spacing()
    margins = layout_margins_height(window.main_layout)
    return top_height + status_height + bottom_height + spacing * 2 + margins


def calculate_compact_min_height(window) -> int:
    return calculate_base_min_height(window)


def calculate_tabs_max_height(window) -> int:
    if not hasattr(window, "tabs"):
        return 0
    max_height = 0
    for index in range(window.tabs.count()):
        page = window.tabs.widget(index)
        if not page:
            continue
        page_height = page.sizeHint().height()
        layout = page.layout()
        if layout:
            layout.activate()
            page_height = max(page_height, layout.sizeHint().height())
        max_height = max(max_height, page_height)
    return max_height


def calculate_expanded_min_height(window) -> int:
    base_height = calculate_base_min_height(window)
    settings_height = 0
    if hasattr(window, "tabs"):
        tab_bar = window.tabs.tabBar()
        tab_bar_height = tab_bar.sizeHint().height()
        tab_margins = window.tabs.contentsMargins()
        frame = window.tabs.style().pixelMetric(QStyle.PM_DefaultFrameWidth)
        content_height = calculate_tabs_max_height(window)
        settings_layout = getattr(window, "settings_layout", None)
        layout_margins = layout_margins_height(
            settings_layout or window.settings_panel.layout()
        )
        settings_height = (
            tab_bar_height
            + content_height
            + tab_margins.top()
            + tab_margins.bottom()
            + frame * 2
            + layout_margins
        )
    spacing = window.main_layout.spacing()
    return base_height + settings_height + spacing


def sync_size_setting(window, key, value, spin_attr) -> None:
    if window.assistant.settings.get(key) != value:
        window.assistant.save_setting(key, value)
    spin = getattr(window, spin_attr, None)
    if spin:
        spin.blockSignals(True)
        spin.setValue(value)
        spin.blockSignals(False)


def apply_width_floor(window, requested_width, mode):
    if mode == "expanded":
        min_width = calculate_expanded_min_width(window)
    else:
        min_width = calculate_compact_min_width(window)
    min_width = max(min_width, 250)
    screen_width = available_screen_width(window)
    if screen_width:
        min_width = min(min_width, screen_width)
    final_width = max(requested_width, min_width)
    if screen_width:
        final_width = min(final_width, screen_width)
    return final_width, min_width


def apply_height_floor(window, requested_height, mode):
    if mode == "expanded":
        min_height = calculate_expanded_min_height(window)
    else:
        min_height = calculate_compact_min_height(window)
    if mode == "expanded":
        min_height = max(min_height, 300)
    else:
        min_height = max(min_height, 100)
    screen_height = available_screen_height(window)
    if screen_height:
        min_height = min(min_height, screen_height)
    final_height = max(requested_height, min_height)
    if screen_height:
        final_height = min(final_height, screen_height)
    return final_height, min_height


def install_autofit_watchers(window) -> None:
    window._autofit_widgets = set()
    if not hasattr(window, "tabs"):
        return
    window.tabs.installEventFilter(window)
    window._autofit_widgets.add(window.tabs)
    for index in range(window.tabs.count()):
        page = window.tabs.widget(index)
        if not page:
            continue
        page.installEventFilter(window)
        window._autofit_widgets.add(page)


def schedule_expanded_autofit(window) -> None:
    if not window.settings_expanded:
        return
    if not hasattr(window, "_autofit_timer"):
        window._autofit_timer = QTimer(window)
        window._autofit_timer.setSingleShot(True)
        window._autofit_timer.timeout.connect(window._apply_expanded_autofit)
    if not window._autofit_timer.isActive():
        window._autofit_timer.start(120)


def apply_expanded_autofit(window) -> None:
    if not window.settings_expanded or window.is_programmatic_resize:
        return
    requested_height = window.height()
    adjusted_height, min_height = apply_height_floor(
        window, requested_height, "expanded"
    )
    if (
        adjusted_height == requested_height
        and min_height == window.minimumHeight()
    ):
        return
    window.is_programmatic_resize = True
    window.setMinimumHeight(min_height)
    window.resize(window.width(), adjusted_height)
    window.is_programmatic_resize = False
    if adjusted_height != requested_height:
        sync_size_setting(
            window, "expanded_height", adjusted_height, "expanded_height_spin"
        )
        log_message(
            "Автоподбор высоты развернутого режима по содержимому: "
            f"{requested_height} -> {adjusted_height}"
        )


def toggle_settings_panel(window) -> None:
    """Переключение между компактным и развернутым режимом."""
    window.is_programmatic_resize = True

    if window.settings_expanded:
        window.settings_panel.hide()
        window.toggle_settings_button.setText("▼")
        window.settings_expanded = False
        target_width = window.assistant.settings.get("compact_width")
        target_height = window.assistant.settings.get("compact_height")
        adjusted_width, min_width = apply_width_floor(
            window, target_width, "compact"
        )
        adjusted_height, min_height = apply_height_floor(
            window, target_height, "compact"
        )
        window.setMinimumSize(min_width, min_height)
        if adjusted_width != target_width:
            sync_size_setting(
                window, "compact_width", adjusted_width, "compact_width_spin"
            )
            log_message(
                "Автоподбор ширины компактного режима: "
                f"{target_width} -> {adjusted_width}"
            )
        if adjusted_height != target_height:
            sync_size_setting(
                window, "compact_height", adjusted_height, "compact_height_spin"
            )
            log_message(
                "Автоподбор высоты компактного режима: "
                f"{target_height} -> {adjusted_height}"
            )
        window.resize(adjusted_width, adjusted_height)
        log_message(
            "Переход в компактный режим. Размер: "
            f"{adjusted_width}x{adjusted_height}"
        )
    else:
        window.settings_expanded = True
        window.settings_panel.show()
        window.toggle_settings_button.setText("▲")
        target_width = window.assistant.settings.get("expanded_width")
        target_height = window.assistant.settings.get("expanded_height")
        adjusted_width, min_width = apply_width_floor(
            window, target_width, "expanded"
        )
        adjusted_height, min_height = apply_height_floor(
            window, target_height, "expanded"
        )
        window.setMinimumSize(min_width, min_height)
        if adjusted_width != target_width:
            sync_size_setting(
                window, "expanded_width", adjusted_width, "expanded_width_spin"
            )
            log_message(
                "Автоподбор ширины развернутого режима: "
                f"{target_width} -> {adjusted_width}"
            )
        if adjusted_height != target_height:
            sync_size_setting(
                window, "expanded_height", adjusted_height, "expanded_height_spin"
            )
            log_message(
                "Автоподбор высоты развернутого режима: "
                f"{target_height} -> {adjusted_height}"
            )
        target_width = adjusted_width
        target_height = adjusted_height

        if window.screen():
            screen_geo = window.screen().availableGeometry()
            current_geo = window.geometry()

            new_x = current_geo.x()
            new_y = current_geo.y()

            if new_x + target_width > screen_geo.right():
                new_x = screen_geo.right() - target_width
            if new_y + target_height > screen_geo.bottom():
                new_y = screen_geo.bottom() - target_height

            if new_x < screen_geo.left():
                new_x = screen_geo.left()
            if new_y < screen_geo.top():
                new_y = screen_geo.top()

            window.move(new_x, new_y)

        window.resize(target_width, target_height)
        log_message(
            f"Переход в развернутый режим. Размер: {target_width}x{target_height}"
        )
    window.is_programmatic_resize = False
