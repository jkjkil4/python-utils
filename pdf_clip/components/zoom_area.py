import sys

sys.path.append('.')

from abc import abstractmethod

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QWidget

from utils.simple import clip

DEFAULT_ZOOM_FACTOR_RANGE = (0.5, 3)
WHEEL_SCALE = 1.1


class AbstractZoomArea(QWidget):
    """
    重要概念：

    坐标系分为 “窗口坐标系” 以及 “视图坐标系”，其中：

    - 窗口坐标系即直接的桌面窗口标架

    - 视图坐标系依赖 `_factor` 和 `_scroll` 与窗口坐标系相转换

    坐标系关联：

    - 视图坐标系的 `x=0` 始终在窗口中居中

    - 视图坐标系的 `y` 依赖 `_factor` 和 `_scroll` 而定，具体参考其行内的注释
    """

    scrolled = Signal()
    zoomed = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._factor_range = DEFAULT_ZOOM_FACTOR_RANGE
        # 页面的缩放系数，数值越大越 Zoom in
        self._factor: float = 1
        # 窗口顶部在视图坐标系中的 y 坐标
        self._scroll: float = 0
        # (y 坐标的 margin, 是否在窗口坐标中考虑)
        self._y_margin = (0, False)

    @abstractmethod
    def get_content_height(self) -> float:
        raise NotImplementedError()

    # region view parameters

    def set_zoom_factor_range(self, min: int, max: int) -> None:
        self._factor_range = (min, max)
        self.set_zoom_factor(self._factor)

    def set_zoom_factor(self, factor: float) -> None:
        self._factor = clip(factor, *self._factor_range)
        self.update()
        self.zoomed.emit()

    def set_y_margin(self, margin: float, on_wnd_coord: bool) -> None:
        self._y_margin = (margin, on_wnd_coord)
        self.set_scroll(self._scroll)

    def set_scroll(self, scroll: float) -> None:
        min_scroll, max_scroll = self.get_scroll_range()

        self._scroll = clip(scroll, min_scroll, max_scroll)
        self.update()
        self.scrolled.emit()

    def get_scroll_range(self) -> tuple[float, float]:
        # 根据 _y_margin 限制 _scroll
        margin, on_wnd_coord = self._y_margin
        content_height = self.get_content_height()
        wnd_height = self.height()
        factor = self._factor

        if on_wnd_coord:
            margin_view = margin / factor
        else:
            margin_view = margin

        # 允许的 scroll 范围：窗口顶部在视图坐标的最小/最大值
        min_scroll = -margin_view
        max_scroll = max(content_height - wnd_height / factor + margin_view, min_scroll)
        return (min_scroll, max_scroll)

    # endregion

    # region coord convert

    def wnd_x_to_view(self, wnd_x: float) -> float:
        return (wnd_x - self.width() / 2) / self._factor

    def wnd_y_to_view(self, wnd_y: float) -> float:
        return wnd_y / self._factor + self._scroll

    def wnd_to_view(self, wnd: tuple[float, float]) -> tuple[float, float]:
        x, y = wnd
        return self.wnd_x_to_view(x), self.wnd_y_to_view(y)

    def qwnd_to_view(self, wnd: QPointF) -> QPointF:
        return QPointF(self.wnd_x_to_view(wnd.x()), self.wnd_y_to_view(wnd.y()))

    def view_x_to_wnd(self, view_x: float) -> float:
        return view_x * self._factor + self.width() / 2

    def view_y_to_wnd(self, view_y: float) -> float:
        return (view_y - self._scroll) * self._factor

    def view_to_wnd(self, view: tuple[float, float]) -> tuple[float, float]:
        x, y = view
        return self.view_x_to_wnd(x), self.view_y_to_wnd(y)

    def qview_to_wnd(self, view: QPointF) -> QPointF:
        return QPointF(self.view_x_to_wnd(view.x()), self.view_y_to_wnd(view.y()))

    # endregion

    def wheelEvent(self, event: QWheelEvent, /) -> None:
        delta = event.angleDelta().y()

        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            view_y_prev = self.wnd_y_to_view(self.height() / 2)

            if delta > 0:
                self.set_zoom_factor(self._factor * WHEEL_SCALE)
            else:
                self.set_zoom_factor(self._factor / WHEEL_SCALE)

            view_y_now = self.wnd_y_to_view(self.height() / 2)
            view_y_delta = view_y_now - view_y_prev
            self.set_scroll(self._scroll - view_y_delta)

            self.update()
        else:
            self.set_scroll(self._scroll - delta / self._factor)


class AbstractNavigatableZoomArea(AbstractZoomArea):
    def current_page_index(self) -> int:
        raise NotImplementedError()

    def scroll_to_page(self, index: int) -> None:
        raise NotImplementedError()

    def page_count(self) -> int:
        raise NotImplementedError()


if __name__ == '__main__':

    class TestZoomArea(AbstractZoomArea):
        N = 9
        SIDE_LENGTH = 200
        SPACING = 20

        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)
            self.set_y_margin(self.SPACING, False)

        def get_content_height(self) -> float:
            # 总高度 = N * SIDE_LENGTH + (N-1) * SPACING
            return self.N * self.SIDE_LENGTH + (self.N - 1) * self.SPACING

        def paintEvent(self, _):
            from PySide6.QtGui import QBrush, QColor, QPainter

            painter = QPainter(self)
            colors = [QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255)]

            for i in range(self.N):
                y_view = i * (self.SIDE_LENGTH + self.SPACING)
                x_view = 0  # 居中
                # 转换到窗口坐标
                x_wnd = self.view_x_to_wnd(x_view - self.SIDE_LENGTH / 2)
                y_wnd = self.view_y_to_wnd(y_view)
                size = self.SIDE_LENGTH * self._factor

                painter.setBrush(QBrush(colors[i % 3]))
                painter.setPen(QColor(0, 0, 0))
                painter.drawRect(QRectF(x_wnd, y_wnd, size, size))

    from utils.qt import exec_widget

    exec_widget(TestZoomArea)
