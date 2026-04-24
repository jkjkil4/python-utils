from __future__ import annotations

import sys
from typing import Generator

sys.path.append('.')

import os
from bisect import bisect

from PySide6.QtCore import QRectF
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from pdf_clip.components.zoom_area import AbstractNavigatableZoomArea
from utils.simple import clip


class PixmapPages(AbstractNavigatableZoomArea):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pages: list[Page] = []

    def get_content_height(self) -> float:
        if not self._pages:
            return 0
        last = self._pages[-1].rect
        return last.y() + last.height()

    def set_pixmaps(self, pixmaps: list[QPixmap], *, scale: float = 1, spacing: float = 20) -> None:
        y = 0
        pages: list[Page] = []
        for pixmap in pixmaps:
            page = Page(pixmap, y, scale)
            pages.append(page)
            y += page.rect.height() + spacing

        self._pages = pages
        self.update()

    def current_page_index(self) -> int:
        idx = bisect(self._pages, self._scroll, key=lambda page: page.rect.y())
        return max(0, idx - 1)

    def scroll_to_page(self, index: int) -> None:
        if not self._pages:
            return
        index = clip(index, 0, len(self._pages) - 1)
        self.set_scroll(self._pages[index].rect.y())

    def page_count(self) -> int:
        return len(self._pages)

    def visible_pages(self) -> Generator[tuple[int, Page], None, None]:
        y0 = self.wnd_y_to_view(0)
        y1 = self.wnd_y_to_view(self.height())

        # 用 bisect 找到第一个需要绘制的页面
        start = bisect(self._pages, y0, key=lambda page: page.rect.y() + page.rect.height())

        for i in range(start, len(self._pages)):
            page = self._pages[i]
            page_top = page.rect.y()
            if page_top > y1:
                return
            yield (i, page)

    def paintEvent(self, _) -> None:
        if not self._pages:
            return
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )

        for _, page in self.visible_pages():
            x_wnd = self.view_x_to_wnd(page.rect.x())
            y_wnd = self.view_y_to_wnd(page.rect.y())
            w = page.rect.width() * self._factor
            h = page.rect.height() * self._factor
            painter.drawPixmap(QRectF(x_wnd, y_wnd, w, h).toRect(), page.pixmap)


class Page:
    def __init__(self, pixmap: QPixmap, y: float, scale: float):
        w = pixmap.width() * scale
        h = pixmap.height() * scale
        self.pixmap = pixmap
        self.rect = QRectF(-w / 2, y, w, h)


if __name__ == '__main__':

    class TestPixmapPages(PixmapPages):
        def __init__(self, parent: QWidget | None = None):
            super().__init__(parent)

            # 读取 ~/Pictures/截图/ 目录下的所有图片文件
            pictures_dir = os.path.expanduser('~/Pictures/截图/')
            image_files = [
                os.path.join(pictures_dir, f)
                for f in os.listdir(pictures_dir)
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))
            ]
            print(f'{len(image_files)=}')
            pixmaps = [QPixmap(path) for path in image_files if os.path.isfile(path)]
            self.set_pixmaps(pixmaps)
            self.set_y_margin(100, True)

    from utils.qt import exec_widget

    exec_widget(TestPixmapPages)
