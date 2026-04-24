from __future__ import annotations

from dataclasses import dataclass
import sys
from typing import TYPE_CHECKING

from PySide6.QtCore import QPointF, QRectF, QSizeF, Signal

from pdf_clip.handlers.selection import SelectionHandler

sys.path.append('.')

import numpy as np
import pymupdf as pdf
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from pdf_clip.components.navigator import Navigator
from pdf_clip.components.pixmap_pages import PixmapPages
from pdf_clip.handlers.quickscroll import QuickScrollHandler


@dataclass
class PagePart:
    index: int
    ratios: np.ndarray
    pixmap: QPixmap


class PDFPages(PixmapPages):
    if TYPE_CHECKING:
        parts_selected = Signal(list[PagePart])
    else:
        parts_selected = Signal(list)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        QuickScrollHandler(self)

        self.select = SelectionHandler(self)
        self.select.dragging.connect(self.update)
        self.select.selected.connect(self.on_selected)

    def load(self, file_path: str) -> bool:
        try:
            doc = pdf.open(file_path)

            # 将每一页转为图像
            pixmaps: list[QPixmap] = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                # 将页面转换为图像（DPI 150 获得足够清晰度）
                pix = page.get_pixmap(matrix=pdf.Matrix(1.5, 1.5))

                # 将 pixmap 转换为 QPixmap
                image_data = pix.tobytes()
                q_image = QImage()
                q_image.loadFromData(image_data)
                q_pixmap = QPixmap.fromImage(q_image)
                pixmaps.append(q_pixmap)

            doc.close()

            self.set_pixmaps(pixmaps)
            return True

        except Exception as e:
            print(f'打开文件出错：{e}')
            return False

    def on_selected(self, selection: QRectF) -> None:
        self.update()

        view_p1 = self.qwnd_to_view(selection.topLeft())
        view_p2 = self.qwnd_to_view(selection.bottomRight())
        view_selection = QRectF(view_p1, view_p2)

        parts: list[PagePart] = []

        for i, page in self.visible_pages():
            intersected = page.rect.intersected(view_selection)
            if intersected.isNull():
                continue
            # 相对于页面的坐标
            p1 = intersected.topLeft() - page.rect.topLeft()
            p2 = intersected.bottomRight() - page.rect.topLeft()

            # x1 y1 x2 y2 在页面中的百分比位置
            ratios = np.array([*p1.toTuple(), *p2.toTuple()])
            ratios[::2] /= page.rect.width()
            ratios[1::2] /= page.rect.height()
            ratios = np.clip(ratios, a_min=0.0, a_max=1.0)

            pixmap = page.pixmap.copy(*self.roundvec(p1), *self.roundvec(intersected.size()))

            parts.append(PagePart(i, ratios, pixmap))

        self.parts_selected.emit(parts)

    @staticmethod
    def roundvec(p: QPointF | QSizeF) -> tuple[int, int]:
        x, y = p.toTuple()
        return (round(x), round(y))

    def paintEvent(self, _) -> None:
        super().paintEvent(_)
        painter = QPainter(self)
        self.select.paint_current_selection(painter)


class PDFViewer(Navigator[PDFPages]):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(PDFPages, parent)
