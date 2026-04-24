import sys

sys.path.append('.')

from PySide6.QtCore import QPointF, QRectF, Signal, QObject, Qt
from PySide6.QtGui import QPainter, QColor, QMouseEvent
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel


class SelectionHandler(QObject):
    dragging = Signal()
    selected = Signal(QRectF)

    def __init__(self, widget: QWidget):
        super().__init__(widget)
        self._select_start_pos: QPointF | None = None
        self._select_end_pos: QPointF | None = None
        widget.installEventFilter(self)

    def get_selection(self) -> QRectF | None:
        if self._select_start_pos is None or self._select_end_pos is None:
            return None
        rect = QRectF(self._select_start_pos, self._select_end_pos).normalized()
        return rect

    def eventFilter(self, obj, event):
        if event.type() == QMouseEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self._select_start_pos = event.position()
                return True
        elif event.type() == QMouseEvent.Type.MouseMove:
            if event.buttons() & Qt.MouseButton.LeftButton:
                self._select_end_pos = event.position()
                self.dragging.emit()
                return True
        elif event.type() == QMouseEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                selection = self.get_selection()
                if selection is not None:
                    self.selected.emit(selection)
                self._select_start_pos = None
                self._select_end_pos = None
                return True
        return super().eventFilter(obj, event)

    def paint_current_selection(self, painter: QPainter) -> None:
        selection = self.get_selection()
        if selection is None:
            return
        painter.fillRect(selection, QColor(0, 0, 255, 30))


if __name__ == '__main__':

    class TestSelectionArea(QWidget):
        def __init__(self):
            super().__init__()
            self.setMinimumSize(400, 300)
            self.selection_handler = SelectionHandler(self)
            self.selection_handler.dragging.connect(self.on_dragging)
            self.selection_handler.selected.connect(self.on_selected)
            self.info_label = QLabel('Drag to select an area', self)
            layout = QVBoxLayout(self)
            layout.addWidget(self.info_label)
            layout.addStretch()

        def on_dragging(self):
            self.update()

        def on_selected(self, rect: QRectF):
            self.info_label.setText(f'Selected: {rect}')
            self.update()

        def paintEvent(self, event):
            super().paintEvent(event)
            painter = QPainter(self)
            self.selection_handler.paint_current_selection(painter)

    from utils.qt import exec_widget

    exec_widget(TestSelectionArea)
