from dataclasses import dataclass
from typing import List

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QWidget
from viewer.scroll_viewer import ScrollViewer


class ImagePagesViewer(ScrollViewer):
    """
    图像页面查看器
    """
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.images: List[QPixmap] = []
        self.scaled_pixmaps: List[QPixmap] = []  # 缩放后的图像缓存

    def set_images(self, images: List[QImage]) -> None:
        """
        设置要显示的图像列表
        """
        self.images = [QPixmap.fromImage(img) for img in images]
        self.scroll_offset = -self.PAGE_SPACING

        # 自动计算缩放因子以适应当前宽度（左右各留 PAGE_SPACING）
        if self.images and self.width() > 0:
            first_image = self.images[0]
            available_width = self.width() - 2 * self.PAGE_SPACING
            self.zoom_factor = available_width / first_image.width()
            # 限制缩放范围
            self.zoom_factor = max(
                self.min_zoom,
                min(self.max_zoom, self.zoom_factor)
            )
        else:
            self.zoom_factor = 1.0

        self.update_scaled_pixmaps()
        self.update()

    def update_scaled_pixmaps(self) -> None:
        """
        根据缩放因子更新所有缩放后的图像缓存
        """
        self.scaled_pixmaps = []
        for pixmap in self.images:
            scaled_width = int(pixmap.width() * self.zoom_factor)
            scaled_height = int(pixmap.height() * self.zoom_factor)
            scaled_pixmap = pixmap.scaled(
                scaled_width,
                scaled_height,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.scaled_pixmaps.append(scaled_pixmap)

    def on_zoom_changed(self) -> None:
        """
        缩放因子改变时更新缩放后的图像缓存
        """
        self.update_scaled_pixmaps()

    def get_content_height(self) -> int:
        """
        获取内容的总高度（实现 ScrollViewer 的抽象方法）
        """
        if not self.images:
            return 0

        total_height = 0
        for pixmap in self.images:
            scaled_height = int(pixmap.height() * self.zoom_factor)
            total_height += scaled_height + self.PAGE_SPACING

        return total_height

    def paintEvent(self, event) -> None:
        """
        绘制所有图像
        """
        if not self.images:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        y_offset = -self.scroll_offset  # 当前绘制的 y 坐标
        widget_height = self.height()

        p.setPen(QColor(200, 200, 200))
        for scaled_pixmap in self.scaled_pixmaps:
            scaled_width, scaled_height = scaled_pixmap.size().toTuple()

            # 计算绘制位置（水平居中）
            x = (self.width() - scaled_pixmap.width()) // 2

            # 只绘制在可见范围内的图像
            if y_offset + scaled_height > 0 and y_offset < widget_height:
                p.drawPixmap(x, y_offset, scaled_pixmap)

            # 绘制页面边框
            p.drawRect(x, int(y_offset), scaled_width, scaled_height)

            y_offset += scaled_height + self.PAGE_SPACING


@dataclass
class SelectedRect:
    page_index: int
    # 以下这四个值都是 0~1 的数，表示占页面尺寸的比例
    x_min: float
    x_max: float
    y_min: float
    y_max: float


class ClipSelectViewer(ImagePagesViewer):
    """
    支持矩形选择的图像查看器
    Ctrl+左键拖动选择矩形，将其转换为 PDF 中的范围并发出信号
    """

    clip_selected = Signal(SelectedRect)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selecting = False
        self.select_start_pos = None
        self.select_end_pos = None

    def get_page_positions(self) -> list[tuple[int, int, float]]:
        """
        获取所有页面在显示中的位置信息
        返回列表，每项为 (y_start, y_end, scaled_width, scaled_height)
        """
        positions = []
        y_offset = -self.scroll_offset

        for pixmap in self.images:
            scaled_width = pixmap.width() * self.zoom_factor
            scaled_height = pixmap.height() * self.zoom_factor

            y_start = y_offset
            y_end = y_offset + scaled_height

            positions.append((y_start, y_end, scaled_width))
            y_offset += scaled_height + self.PAGE_SPACING

        return positions

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier and \
                event.button() == Qt.MouseButton.LeftButton:
            # Ctrl+左键开始选择
            self.selecting = True
            self.select_start_pos = event.pos()
            self.select_end_pos = event.pos()
        else:
            # 普通左键拖动滚动
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.selecting:
            self.select_end_pos = event.pos()
            self.update()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.selecting and \
                event.button() == Qt.MouseButton.LeftButton:
            assert self.select_start_pos is not None
            assert self.select_end_pos is not None

            self.selecting = False

            # 过滤移动距离过短的（所有方向上的移动量小于4）
            delta = self.select_end_pos - self.select_start_pos
            if abs(delta.x()) < 4 and abs(delta.y()) < 4:
                self.update()
                return

            self.process_selection(self.select_start_pos, self.select_end_pos)
            self.update()

    def process_selection(self, select_start_pos: QPoint, select_end_pos: QPoint) -> None:
        """
        处理矩形选择
        """
        # 获取矩形范围
        x1, y1 = select_start_pos.toTuple()
        x2, y2 = select_end_pos.toTuple()

        rect_left = min(x1, x2)
        rect_right = max(x1, x2)
        rect_top = min(y1, y2)
        rect_bottom = max(y1, y2)

        # 获取矩形涉及的所有页面
        positions = self.get_page_positions()

        for page_index, (y_start, y_end, scaled_width) in enumerate(positions):
            # 检查矩形是否与此页面相交
            if rect_bottom < y_start or rect_top > y_end:
                continue

            # 限制矩形到页面范围
            page_x_start = (self.width() - scaled_width) // 2
            page_x_end = page_x_start + scaled_width

            # 检查矩形 x 范围是否完全在页面外
            if rect_right < page_x_start or rect_left > page_x_end:
                continue

            clipped_left = max(rect_left, page_x_start)
            clipped_right = min(rect_right, page_x_end)
            clipped_top = max(rect_top, y_start)
            clipped_bottom = min(rect_bottom, y_end)

            x_min = (clipped_left - page_x_start) / (page_x_end - page_x_start)
            x_max = (clipped_right - page_x_start) / (page_x_end - page_x_start)
            y_min = (clipped_top - y_start) / (y_end - y_start)
            y_max = (clipped_bottom - y_start) / (y_end - y_start)

            self.clip_selected.emit(SelectedRect(page_index, x_min, x_max, y_min, y_max))

    def paintEvent(self, event) -> None:
        """
        绘制所有图像和选择矩形
        """
        super().paintEvent(event)

        # 绘制选择矩形
        if self.selecting and self.select_start_pos is not None and \
                self.select_end_pos is not None:

            painter = QPainter(self)

            x1 = self.select_start_pos.x()
            y1 = self.select_start_pos.y()
            x2 = self.select_end_pos.x()
            y2 = self.select_end_pos.y()

            rect = QRect(min(x1, x2), min(y1, y2), abs(x2 - x1),
                         abs(y2 - y1))

            # 绘制矩形边框
            painter.drawRect(rect)

            # 绘制半透明填充
            painter.fillRect(rect, QColor(0, 0, 255, 30))
