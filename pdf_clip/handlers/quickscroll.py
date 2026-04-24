from PySide6.QtCore import QObject
from PySide6.QtGui import QMouseEvent, Qt

from pdf_clip.components.zoom_area import AbstractZoomArea


class QuickScrollHandler(QObject):
    def __init__(self, widget: AbstractZoomArea):
        super().__init__(widget)
        widget.installEventFilter(self)
        self._widget = widget

    def eventFilter(self, obj, event):
        if event.type() in (QMouseEvent.Type.MouseButtonPress, QMouseEvent.Type.MouseMove):
            if event.buttons() & Qt.MouseButton.MiddleButton:
                self.on_quickscroll(event.position().y())
                return True
        return super().eventFilter(obj, event)

    def on_quickscroll(self, y: float) -> None:
        factor = y / self._widget.height()
        scroll_min, scroll_max = self._widget.get_scroll_range()

        scroll = (1 - factor) * scroll_min + factor * scroll_max
        self._widget.set_scroll(scroll)
