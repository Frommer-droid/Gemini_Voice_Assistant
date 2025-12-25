"""Помощник для прилипания окна к краям экрана."""

from PySide6.QtCore import QRect


def snap_to_screen(widget, threshold: int = 20):
    """
    Притягивает окно к краям доступной области экрана, если оно вблизи threshold.
    Работает и для frameless окон.
    """
    try:
        screen = widget.screen()
        if not screen:
            return

        screen_geo: QRect = screen.availableGeometry()
        geo: QRect = widget.frameGeometry()

        x, y = geo.x(), geo.y()
        w, h = geo.width(), geo.height()

        if abs(geo.left() - screen_geo.left()) <= threshold:
            x = screen_geo.left()
        elif abs(screen_geo.right() - geo.right()) <= threshold:
            x = screen_geo.right() - w

        if abs(geo.top() - screen_geo.top()) <= threshold:
            y = screen_geo.top()
        elif abs(screen_geo.bottom() - geo.bottom()) <= threshold:
            y = screen_geo.bottom() - h

        if (x, y) != (geo.x(), geo.y()):
            widget.move(x, y)
    except Exception:
        # Если что-то пошло не так, просто не трогаем позицию.
        pass
