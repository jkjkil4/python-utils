import sys

from PySide6.QtCore import QMargins

sys.path.append('.')

import os

from PySide6.QtWidgets import QFileDialog, QFrame, QHBoxLayout, QMainWindow, QMessageBox, QWidget

from pdf_clip.constants import PIXMAP_SIZE
from pdf_clip.viewers.output_viewer import OutputViewer
from pdf_clip.viewers.pdf_viewer import PagePart, PDFViewer


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setup_widgets()
        self.setup_menubar()
        self.setup_slots()

        self.resize(1200, 800)
        self.setWindowTitle('pdf-clip')

        self._source: tuple[str, float] | None = None

    def setup_widgets(self) -> None:
        self.pdf_viewer = PDFViewer()
        self.output_viewer = OutputViewer()

        self.sep = QFrame()
        self.sep.setFrameShape(QFrame.Shape.VLine)

        self.hlayout = QHBoxLayout()
        self.hlayout.setContentsMargins(QMargins())
        self.hlayout.setSpacing(0)
        self.hlayout.addWidget(self.pdf_viewer, 1)
        self.hlayout.addWidget(self.sep)
        self.hlayout.addWidget(self.output_viewer, 1)

        self.cwidget = QWidget()
        self.cwidget.setLayout(self.hlayout)

        self.setCentralWidget(self.cwidget)

    def setup_menubar(self) -> None:
        menubar = self.menuBar()

        self.menu_files = menubar.addMenu('文件(&F)')

        self.act_open = self.menu_files.addAction('打开(&O)')
        self.act_open.setShortcut('Ctrl+O')

        self.act_export = self.menu_files.addAction('导出(&S)')
        self.act_export.setShortcut('Ctrl+S')

    def setup_slots(self) -> None:
        self.act_open.triggered.connect(self.on_open_file)
        self.act_export.triggered.connect(self.on_export_file)
        self.pdf_viewer.pages_view.parts_selected.connect(self.on_parts_selected)

    def on_open_file(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(self, '打开 PDF 文件', '', 'PDF 文件 (*.pdf)')
        if not file_path:
            return

        self.pdf_viewer.pages_view.load(file_path)
        self.output_viewer.pages_view.clear()

        mtime = os.path.getmtime(file_path)
        self._source = (file_path, mtime)

    def on_parts_selected(self, parts: list[PagePart]) -> None:
        for part in parts:
            mid_ratio = (part.ratios[0] + part.ratios[2]) / 2
            left = -PIXMAP_SIZE[0] / 2
            right = PIXMAP_SIZE[0] / 2
            center_x = (1 - mid_ratio) * left + mid_ratio * right
            origin_x = center_x - part.pixmap.width() / 2
            self.output_viewer.pages_view.stack_element(
                part.index, part.ratios, part.pixmap, origin_x
            )

    def on_export_file(self) -> None:
        if not self.output_viewer.pages_view.has_element():
            QMessageBox.information(self, '提示', '尚未截取内容，无法导出')
            return

        assert self._source is not None
        source_file, source_mtime = self._source

        dir_name = os.path.dirname(source_file)
        file_name = os.path.basename(source_file)
        name, _ = os.path.splitext(file_name)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            '保存 PDF 文件',
            os.path.join(dir_name, f'{name}_clip.pdf'),
            'PDF 文件 (*.pdf)',
        )
        if not file_path:
            return
        mtime = os.path.getmtime(source_file)

        if mtime != source_mtime:
            ret = QMessageBox.warning(self, '警告', '原文件在编辑期间被修改，确认继续导出吗？')
            if ret == QMessageBox.StandardButton.Cancel:
                return

        self.output_viewer.pages_view.save(source_file, file_path)

        QMessageBox.information(self, '提示', '导出已完成')
