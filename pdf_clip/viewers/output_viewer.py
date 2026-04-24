from __future__ import annotations

import sys

sys.path.append('.')

import math
import traceback
from dataclasses import dataclass
from typing import Literal, overload

import numpy as np
import pymupdf as pdf
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from pdf_clip.components.navigator import Navigator
from pdf_clip.components.zoom_area import AbstractNavigatableZoomArea
from pdf_clip.constants import PDF_PAGE_SIZE, PIXMAP_SIZE
from utils.simple import clip


class OutputPages(AbstractNavigatableZoomArea):
    SPACING = 20

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._pages: list[list[PageElement]] = []

        self._hovering: tuple[int, int, PageElement] | None = None

        self._dragging: PageElement | None = None
        self._drag_start: QPointF | None = None
        self._drag_end: QPointF | None = None

        self.setMouseTracking(True)

    # region page stack

    def _ensure_page(self, page: int) -> list[PageElement]:
        while self.page_count() <= page:
            self._pages.append([])
        return self._pages[page]

    def _clean_empty_page(self) -> None:
        for i in range(self.page_count() - 1, -1, -1):
            if not self._pages[i]:
                self._pages.pop()

    def _get_last_element(self) -> tuple[int, PageElement] | None:  # i indicates pageindex
        for i in range(self.page_count() - 1, -1, -1):
            if self._pages[i]:
                elements = sorted(self._pages[i], key=lambda elem: elem.bottom)
                return i, elements[-1]

        return None

    def stack_element(
        self, pdf_page_index: int, pdf_page_ratios: np.ndarray, pixmap: QPixmap, origin_x: float
    ) -> None:
        last = self._get_last_element()
        if last is None:
            page = 0
            origin_y = 0
        else:
            last_page, last_elem = last
            page = last_page
            origin_y = last_elem.bottom
            if origin_y + pixmap.height() > self.get_bottom_of_page(page):
                page += 1
                origin_y = self.get_top_of_page(page)

        self._ensure_page(page).append(
            PageElement(pdf_page_index, pdf_page_ratios, pixmap, QPointF(origin_x, origin_y))
        )
        self.update()

    # endregion

    # region reset / save page

    def clear(self) -> None:
        self._pages.clear()
        self.update()

    def has_element(self) -> bool:
        return any(self._pages)

    def save(self, src_file: str, target_file: str) -> None:
        try:
            doc = pdf.open(src_file)
            new_doc = pdf.open()

            for page_index, elements in enumerate(self._pages):
                target_page = new_doc.new_page(
                    width=PDF_PAGE_SIZE[0],
                    height=PDF_PAGE_SIZE[1],
                )

                for elem in elements:
                    src_page = doc[elem.pdf_page_index]
                    target_page.show_pdf_page(
                        self._get_target_rect(target_page, page_index, elem),
                        doc,
                        elem.pdf_page_index,
                        clip=self._get_src_rect(src_page, elem.pdf_page_ratios),
                    )

            new_doc.save(target_file)
            new_doc.close()
            doc.close()

        except Exception as e:
            print(f'导出文件出错：{e}')
            traceback.print_exc()

    @staticmethod
    def _get_src_rect(pdf_page: pdf.Page, ratios: np.ndarray) -> pdf.Rect:
        pgwidth = pdf_page.rect.width
        pgheight = pdf_page.rect.height
        coords = ratios * [pgwidth, pgheight, pgwidth, pgheight]
        return pdf.Rect(*coords)

    def _get_target_rect(self, pdf_page: pdf.Page, page_index: int, elem: PageElement) -> pdf.Rect:
        pw, ph = PIXMAP_SIZE

        left = -pw / 2
        top = self.get_top_of_page(page_index)
        x = elem.origin.x() - left
        y = elem.origin.y() - top

        rect = QRectF(QPointF(x, y), elem.pixmap.size())
        p1 = rect.topLeft()
        p2 = rect.bottomRight()
        view_coords = np.array([*p1.toTuple(), *p2.toTuple()])

        pgwidth = pdf_page.rect.width
        pgheight = pdf_page.rect.height
        coords = view_coords / [pw, ph, pw, ph] * [pgwidth, pgheight, pgwidth, pgheight]
        return pdf.Rect(*coords)

    # endregion

    # region dragging

    def mousePressEvent(self, event: QMouseEvent, /) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            if self._hovering is None:
                return
            pageindex, elemindex, elem = self._hovering
            self._hovering = None
            del self._pages[pageindex][elemindex]

            self._dragging = elem
            self._drag_start = self.qwnd_to_view(event.position())
            self._drag_end = self._drag_start
            self.update()
        elif event.button() == Qt.MouseButton.RightButton:
            if self._hovering is None:
                return
            pageindex, elemindex, _ = self._hovering
            del self._pages[pageindex][elemindex]
            self._update_hovering()

            self.update()

    def mouseMoveEvent(self, event: QMouseEvent, /) -> None:
        if not event.buttons() & Qt.MouseButton.LeftButton:
            self._update_hovering()
            return

        self._drag_end = self.qwnd_to_view(event.position())
        if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
            assert self._drag_start is not None
            drag_offset = self._drag_end - self._drag_start
            dx = abs(drag_offset.x())
            dy = abs(drag_offset.y())
            if dx > dy:
                self._drag_end.setY(self._drag_start.y())
            else:
                self._drag_end.setX(self._drag_start.x())

        self.update()

    def mouseReleaseEvent(self, event: QMouseEvent, /) -> None:
        if not event.button() == Qt.MouseButton.LeftButton:
            return
        if self._dragging is None:
            return

        assert self._drag_start is not None and self._drag_end is not None

        elem = self._dragging
        self._dragging = None

        drag_offset = self._drag_end - self._drag_start
        page = self.get_page_of_y(self._drag_end.y(), none_in_spacing=False)
        self._drag_start = None
        self._drag_end = None

        elem.origin += drag_offset
        self._ensure_page(page).append(elem)

        self._update_hovering()
        self.update()

    def get_hovering_element(
        self,
    ) -> tuple[int, int, PageElement] | None:  # int, int indicates pageindex and elemindex
        wnd_pos = self.mapFromGlobal(self.cursor().pos())
        view_pos = self.qwnd_to_view(QPointF(wnd_pos))

        pageindex = self.get_page_of_y(view_pos.y(), none_in_spacing=True)
        if pageindex is None:
            return None
        page = self._pages[pageindex]

        for i in range(len(page) - 1, -1, -1):
            elem = page[i]

            if QRectF(elem.origin, elem.pixmap.size()).contains(view_pos):
                return (pageindex, i, elem)

        return None

    def _update_hovering(self) -> None:
        prev = self._hovering
        self._hovering = self.get_hovering_element()
        if self._hovering is not prev:
            self.update()

    # endregion

    # region relation between y and pageindex

    @property
    def unit(self) -> float:
        return PIXMAP_SIZE[1] + self.SPACING

    def get_top_of_page(self, index: int) -> float:
        return self.unit * index

    def get_bottom_of_page(self, index: int) -> float:
        return self.unit * index + PIXMAP_SIZE[1]

    @overload
    def get_page_of_y(self, view_y: float, *, none_in_spacing: Literal[True]) -> int | None: ...
    @overload
    def get_page_of_y(self, view_y: float, *, none_in_spacing: Literal[False]) -> int: ...

    def get_page_of_y(
        self, view_y: float, *, none_in_spacing: Literal[True, False] = True
    ) -> int | None:
        div = math.floor(view_y // self.unit)
        mod = view_y % self.unit
        if none_in_spacing:
            if mod > PIXMAP_SIZE[1] or div < 0 or div >= self.page_count():
                return None
        return clip(div, 0, self.page_count() - 1)

    # endregion

    # region implementations

    def get_content_height(self) -> float:
        return self.get_bottom_of_page(self.page_count() - 1)

    def current_page_index(self) -> int:
        idx = math.floor(self._scroll // self.unit)
        return clip(idx, 0, self.page_count() - 1)

    def scroll_to_page(self, index: int) -> None:
        self.set_scroll(self.get_top_of_page(index))

    def page_count(self) -> int:
        return len(self._pages)

    # endregion

    def paintEvent(self, _) -> None:
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform
        )

        y1 = self.wnd_y_to_view(self.height())

        for i in range(self.current_page_index(), self.page_count()):
            top = self.get_top_of_page(i)
            if top > y1:
                break
            left = -PIXMAP_SIZE[0] / 2
            right = PIXMAP_SIZE[0] / 2
            bottom = top + PIXMAP_SIZE[1]
            p1 = self.qview_to_wnd(QPointF(left, top))
            p2 = self.qview_to_wnd(QPointF(right, bottom))

            painter.fillRect(QRectF(p1, p2), Qt.GlobalColor.white)

            for elem in self._pages[i]:
                self.draw_view_pixmap(painter, elem.origin, elem.pixmap)

        if self._hovering is not None:
            elem = self._hovering[-1]
            pos = self.qview_to_wnd(elem.origin)
            size = elem.pixmap.size() * self._factor
            painter.setPen(QColor(128, 200, 255))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(QRectF(pos, size))

        if self._dragging is not None:
            assert self._drag_start is not None and self._drag_end is not None
            drag_offset = self._drag_end - self._drag_start
            origin = self._dragging.origin + drag_offset

            self.draw_view_pixmap(painter, origin, self._dragging.pixmap)

    def draw_view_pixmap(self, painter: QPainter, origin: QPointF, pixmap: QPixmap) -> None:
        pos = self.qview_to_wnd(origin)
        size = pixmap.size() * self._factor
        painter.drawPixmap(QRectF(pos, size).toRect(), pixmap)


@dataclass
class PageElement:
    pdf_page_index: int
    pdf_page_ratios: np.ndarray
    pixmap: QPixmap
    origin: QPointF

    @property
    def bottom(self) -> float:
        return self.origin.y() + self.pixmap.height()


class OutputViewer(Navigator[OutputPages]):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(OutputPages, parent)
