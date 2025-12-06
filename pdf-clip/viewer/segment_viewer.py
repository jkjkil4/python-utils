import copy
from dataclasses import dataclass, field

from PySide6.QtCore import QPoint, QSize, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QWidget
from viewer.image_pages_viewer import ScrollViewer, SelectedRect

type PageGeometry = QSize


@dataclass
class Segment:
    selected_rect: SelectedRect
    clipped_pixmap: QPixmap

    target_rect: SelectedRect = field(init=False)

    # 这两个值也是 0~1 的数，表示比例
    x_offset: float = 0
    y_offset: float = 0

    def __post_init__(self):
        self.target_rect = copy.copy(self.selected_rect)


class SegmentViewer(ScrollViewer):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.pages: list[PageGeometry] = []
        self.segments: list[Segment] = []
        self.scaled_segments: list[QPixmap] = []  # 缓存缩放后的图像
        self.page_rects: list[tuple[int, int, int, int, int]] = []  # 缓存页面位置信息
        self.hovered_segment_index: int | None = None  # 当前鼠标悬浮的 segment 索引
        self.dragging_segment: bool = False
        self.setMouseTracking(True)  # 使得 mouseMoveEvent 能在没有按下的时候也能响应

    def get_content_height(self) -> int:
        """
        计算所有页面的总高度
        """
        if not self.pages:
            return 0

        total_height = 0
        for page_rect in self.pages:
            scaled_height = int(page_rect.height() * self.zoom_factor)
            total_height += scaled_height + self.PAGE_SPACING

        return total_height

    def pages_count(self) -> int:
        return len(self.pages)

    def add_page(self, rect: PageGeometry) -> None:
        is_first_page = len(self.pages) == 0
        self.pages.append(rect)

        # 如果是第一个页面，自动计算缩放因子以适应当前宽度
        if is_first_page and self.width() > 0:
            available_width = self.width() - 2 * self.PAGE_SPACING
            self.zoom_factor = available_width / rect.width()
            # 限制缩放范围
            self.zoom_factor = max(
                self.min_zoom,
                min(self.max_zoom, self.zoom_factor)
            )
            # 初始化偏移
            self.scroll_offset = -self.PAGE_SPACING

        self.update_page_rects()
        self.update()

    def add_segment(self, segment: Segment) -> None:
        self.segments.append(segment)
        self.update_scaled_segments()
        self.update()

    def clear(self) -> None:
        self.pages.clear()
        self.segments.clear()
        self.update_page_rects()
        self.update_scaled_segments()
        self.update()

    def on_zoom_changed(self) -> None:
        """缩放改变时更新缓存的缩放图像和页面位置"""
        self.update_scaled_segments()
        self.update_page_rects()

    def on_scroll_changed(self) -> None:
        """滚动改变时更新页面位置"""
        self.update_page_rects()

    def update_scaled_segments(self) -> None:
        """更新所有 segments 的缩放图像缓存"""
        self.scaled_segments = []
        for segment in self.segments:
            img_width = int(segment.clipped_pixmap.width() * self.zoom_factor)
            img_height = int(segment.clipped_pixmap.height() * self.zoom_factor)
            scaled = segment.clipped_pixmap.scaled(
                img_width, img_height,
                aspectMode=Qt.AspectRatioMode.KeepAspectRatio,
                mode=Qt.TransformationMode.SmoothTransformation
            )
            self.scaled_segments.append(scaled)

    def update_page_rects(self) -> None:
        """更新所有页面位置信息缓存"""
        self.page_rects = []
        y_offset = -self.scroll_offset

        for page_index, page_rect in enumerate(self.pages):
            scaled_width = int(page_rect.width() * self.zoom_factor)
            scaled_height = int(page_rect.height() * self.zoom_factor)
            x = (self.width() - scaled_width) // 2
            self.page_rects.append((page_index, x, int(y_offset), scaled_width, scaled_height))
            y_offset += scaled_height + self.PAGE_SPACING

    def paintEvent(self, event) -> None:
        """
        绘制所有空白页面和裁剪的图像
        """
        if not self.pages:
            return

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        widget_height = self.height()

        # 绘制白色背景页面
        for page_index, px, py, pw, ph in self.page_rects:
            # 只绘制在可见范围内的页面
            if py + ph > 0 and py < widget_height:
                p.fillRect(px, py, pw, ph, QColor(255, 255, 255))

        # 绘制所有 segments
        for index, segment in enumerate(self.segments):
            if index >= len(self.scaled_segments):
                break

            page_index = segment.target_rect.page_index
            # 找到对应的页面位置信息
            for pi, px, py, pw, ph in self.page_rects:
                if pi == page_index:
                    # 计算图像在页面中的位置
                    img_x = px + int(segment.target_rect.x_min * pw)
                    img_y = py + int(segment.target_rect.y_min * ph)

                    # 使用缓存的缩放图像
                    scaled_pixmap = self.scaled_segments[index]
                    p.drawPixmap(img_x, img_y, scaled_pixmap)
                    break

        # 给当前鼠标悬浮的 segment 绘制边框
        if self.hovered_segment_index is not None:
            segment = self.segments[self.hovered_segment_index]
            page_index = segment.target_rect.page_index

            for pi, px, py, pw, ph in self.page_rects:
                if pi == page_index:
                    img_x = px + int(segment.target_rect.x_min * pw)
                    img_y = py + int(segment.target_rect.y_min * ph)

                    if self.dragging_segment:
                        offset = self.get_segment_dragging_offset()
                        img_x += offset.x()
                        img_y += offset.y()

                    scaled_pixmap = self.scaled_segments[self.hovered_segment_index]
                    # 绘制蓝色边框
                    p.setPen(QColor(50, 150, 255))
                    p.drawRect(img_x, img_y, scaled_pixmap.width(), scaled_pixmap.height())
                    break

        # 最后绘制所有页面边框，避免被图像覆盖
        p.setPen(QColor(200, 200, 200))
        for _, px, py, pw, ph in self.page_rects:
            p.drawRect(px, py, pw, ph)

    def get_hovered_segment(self, mouse_pos) -> int | None:
        """获取鼠标悬浮的 segment 索引（从后往前查找，返回最上层的）"""
        if not self.pages or not self.segments:
            return None

        # 从后往前查找（后添加的在上层）
        for segment_index in range(len(self.segments) - 1, -1, -1):
            if segment_index >= len(self.scaled_segments):
                continue

            segment = self.segments[segment_index]
            page_index = segment.target_rect.page_index

            for pi, px, py, pw, ph in self.page_rects:
                if pi == page_index:
                    img_x = px + int(segment.target_rect.x_min * pw)
                    img_y = py + int(segment.target_rect.y_min * ph)
                    scaled_pixmap = self.scaled_segments[segment_index]
                    img_width = scaled_pixmap.width()
                    img_height = scaled_pixmap.height()

                    # 检查鼠标是否在这个 segment 区域内
                    if (img_x <= mouse_pos.x() <= img_x + img_width and
                            img_y <= mouse_pos.y() <= img_y + img_height):
                        return segment_index
                    break

        return None

    def mousePressEvent(self, event: QMouseEvent):
        if self.hovered_segment_index is not None \
                and event.button() == Qt.MouseButton.LeftButton \
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            self.dragging_segment = True
            self.segment_drag_start_pos = event.pos()
            self.segment_drag_end_pos = event.pos()

        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self.dragging_segment:
            self.segment_drag_end_pos = event.pos()
            self.update()

        else:
            old_hovered = self.hovered_segment_index
            self.hovered_segment_index = self.get_hovered_segment(event.pos())

            # 只在悬浮状态改变时重绘
            if old_hovered != self.hovered_segment_index:
                self.update()

            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self.dragging_segment:
            self.dragging_segment = False

            assert self.hovered_segment_index is not None

            current_page_index = self.get_current_page_index(event.pos())
            if current_page_index is None:
                self.update()
                return

            segment = self.segments[self.hovered_segment_index]
            target = segment.target_rect

            if target.page_index != current_page_index:
                target.page_index = current_page_index
                x_offset = 0.5 - (target.x_min + target.x_max) / 2
                y_offset = 0.5 - (target.y_min + target.y_max) / 2

            else:
                scaled = self.scaled_segments[self.hovered_segment_index]
                scaled_factor = scaled.width() / segment.clipped_pixmap.width()

                page_size = self.pages[segment.selected_rect.page_index]
                scaled_page_size = page_size * scaled_factor

                offset = self.get_segment_dragging_offset()
                x_offset = offset.x() / scaled_page_size.width()
                y_offset = offset.y() / scaled_page_size.height()

            target.x_min += x_offset
            target.x_max += x_offset
            target.y_min += y_offset
            target.y_max += y_offset

            self.update()

        else:
            super().mouseReleaseEvent(event)

    def get_segment_dragging_offset(self) -> QPoint:
        offset = self.segment_drag_end_pos - self.segment_drag_start_pos
        if abs(offset.x()) > abs(offset.y()):
            offset.setY(0)
        else:
            offset.setX(0)
        return offset

    def get_current_page_index(self, pos: QPoint) -> int | None:
        for pi, px, py, pw, ph in self.page_rects:
            if 0 <= pos.x() - px <= pw and 0 <= pos.y() - py <= ph:
                return pi
        return None
