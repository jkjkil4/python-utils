from PySide6.QtCore import Qt
from PySide6.QtGui import QMouseEvent, QWheelEvent
from PySide6.QtWidgets import QWidget


class ScrollViewer(QWidget):
    """
    可滚动视图基类，支持缩放功能
    """
    PAGE_SPACING = 10

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.scroll_offset = -self.PAGE_SPACING  # 纵向滚动偏移
        self.zoom_factor = 1.0
        self.min_zoom = 0.1
        self.max_zoom = 5.0
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def get_content_height(self) -> int:
        """
        获取内容的总高度（需要子类实现）
        """
        raise NotImplementedError()

    def on_zoom_changed(self) -> None:
        """
        缩放因子改变时的回调（子类可以重写以更新内容）
        """
        pass

    def on_scroll_changed(self) -> None:
        """
        滚动偏移改变时的回调（子类可以重写以更新内容）
        """
        pass

    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            # Ctrl + 滚轮缩放
            delta = event.angleDelta().y()
            zoom_step = 1.1

            # 记录缩放前的参数
            old_zoom = self.zoom_factor
            old_scroll_offset = self.scroll_offset

            # 计算缩放中心（视口中心）
            center_y = self.height() // 2

            # 缩放前，视口中心对应的内容 y 坐标
            content_y_before = center_y + old_scroll_offset

            # 更新缩放因子
            if delta > 0:
                self.zoom_factor *= zoom_step
            else:
                self.zoom_factor /= zoom_step

            # 限制缩放范围
            self.zoom_factor = max(
                self.min_zoom,
                min(self.max_zoom, self.zoom_factor)
            )

            # 缩放后，同一个内容位置的新坐标
            # 高度缩放比例
            scale_ratio = self.zoom_factor / old_zoom
            content_y_after = content_y_before * scale_ratio

            # 调整滚动偏移，使得视口中心始终对应同一内容位置
            self.scroll_offset = int(content_y_after - center_y)

            # 重新限制滚动偏移
            self.clamp_scroll_offset()
            # 通知子类缩放已改变
            self.on_zoom_changed()
            self.update()
        else:
            # 普通滚轮滚动
            delta = event.angleDelta().y()
            self.scroll_offset -= delta  # 向上滚动为正
            self.clamp_scroll_offset()
            self.on_scroll_changed()
            self.update()

    def clamp_scroll_offset(self) -> None:
        """
        限制滚动偏移在有效范围内，上下各留出 height() / 2 的滚动量
        """
        total_height = self.get_content_height()
        # 最大允许值为 总高度 - height()/2
        max_offset = max(0, total_height - self.height() // 2)
        # 最小允许值为 -height() / 2（顶部留白）
        min_offset = -self.height() // 2
        self.scroll_offset = max(min_offset, min(self.scroll_offset, max_offset))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.drag_start_pos = event.pos()
            self.drag_start_offset = self.scroll_offset

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if hasattr(self, 'drag_start_pos') and \
                event.buttons() == Qt.MouseButton.LeftButton:
            delta_y = event.pos().y() - self.drag_start_pos.y()
            self.scroll_offset = self.drag_start_offset - delta_y
            self.clamp_scroll_offset()
            self.on_scroll_changed()
            self.update()
