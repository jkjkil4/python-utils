import os
import traceback

import pymupdf as pdf
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMainWindow, QWidget
from viewer.image_pages_viewer import ClipSelectViewer, SelectedRect
from viewer.segment_viewer import Segment, SegmentViewer


class MainWindow(QMainWindow):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setup_menu()
        self.setup_ui()
        self.setWindowTitle('pdf-clip')

        self.file_path: str | None = None

    def setup_menu(self) -> None:
        self.menu_files = self.menuBar().addMenu('文件')

        self.action_open = self.menu_files.addAction('打开 PDF 文件')
        self.action_open.setShortcut('Ctrl+O')
        self.action_open.setAutoRepeat(False)
        self.action_open.triggered.connect(self.on_open_file)

        self.action_export = self.menu_files.addAction('导出 PDF 文件')
        self.action_export.setShortcut('Ctrl+S')
        self.action_export.setAutoRepeat(False)
        self.action_export.triggered.connect(self.on_export_file)

    def setup_ui(self) -> None:
        # 创建中央部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 创建水平布局
        layout = QHBoxLayout(central_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # 创建左侧 ClipSelectViewer（支持矩形选择）
        self.viewer_left = ClipSelectViewer()
        self.viewer_left.clip_selected.connect(self.on_clip_selected)

        # 创建右侧 SegmentViewer
        self.viewer_right = SegmentViewer()

        layout.addWidget(self.viewer_left, 1)
        layout.addWidget(self.viewer_right, 1)

        # 设置窗口大小
        self.resize(1400, 900)

    def on_open_file(self) -> None:
        """
        打开 PDF 文件并转换为图像
        """
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            '打开 PDF 文件',
            '',
            'PDF 文件 (*.pdf)'
        )

        if not file_path:
            return

        try:
            doc = pdf.open(file_path)

            # 将每一页转为图像
            images = []
            for page_num in range(len(doc)):
                page = doc[page_num]
                # 将页面转换为图像（DPI 150 获得足够清晰度）
                pix = page.get_pixmap(matrix=pdf.Matrix(1.5, 1.5))

                # 将 pixmap 转换为 QImage
                image_data = pix.tobytes("ppm")
                q_image = QImage()
                q_image.loadFromData(image_data)
                images.append(q_image)

            doc.close()

            self.viewer_left.set_images(images)
            self.viewer_right.clear()

            self.file_path = file_path

        except Exception as e:
            print(f'打开文件出错: {e}')

    def on_clip_selected(self, rect: SelectedRect) -> None:
        """
        处理矩形选择信号
        """
        # 如果在 SegmentViewer 中没有足够的页面 (diff>0)，则创建
        for i in range(self.viewer_right.pages_count(), rect.page_index + 1):
            self.viewer_right.add_page(self.viewer_left.images[i].size())

        # 根据 rect 的范围截取图像
        source_pixmap = self.viewer_left.images[rect.page_index]
        source_width = source_pixmap.width()
        source_height = source_pixmap.height()

        # 计算实际像素坐标
        x = int(rect.x_min * source_width)
        y = int(rect.y_min * source_height)
        width = int((rect.x_max - rect.x_min) * source_width)
        height = int((rect.y_max - rect.y_min) * source_height)

        # 截取图像
        clipped = source_pixmap.copy(x, y, width, height)

        # 传递 Segment
        self.viewer_right.add_segment(Segment(rect, clipped))

    def on_export_file(self) -> None:
        if not self.file_path:
            return

        dir_name = os.path.dirname(self.file_path)
        file_name = os.path.basename(self.file_path)
        name, _ = os.path.splitext(file_name)

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            '导出 PDF 文件',
            os.path.join(dir_name, f'{name}_clip.pdf'),
            'PDF 文件 (*.pdf)'
        )

        if not file_path:
            return

        segments = self.viewer_right.segments
        if not segments:
            return

        # 按页面顺序遍历，遇到新页面时再创建 new_page（pymupdf new_page 需顺序创建）
        segments_sorted = sorted(segments, key=lambda t: t.target_rect.page_index)

        try:
            doc = pdf.open(self.file_path)
            new_doc = pdf.open()

            current_page_index = -1
            current_page = None

            for segment in segments_sorted:
                page_index = segment.selected_rect.page_index
                target_page_index = segment.target_rect.page_index

                # 进入新页面时创建对应的新页
                if target_page_index != current_page_index:
                    source_page = doc[target_page_index]
                    current_page = new_doc.new_page(
                        width=source_page.rect.width,
                        height=source_page.rect.height
                    )
                    current_page_index = target_page_index

                current_page.show_pdf_page(
                    self.get_pdf_rect(current_page, segment.target_rect),
                    doc,
                    page_index,
                    clip=self.get_pdf_rect(current_page, segment.selected_rect)
                )

            new_doc.save(file_path)
            new_doc.close()
            doc.close()

        except Exception as e:
            print(f'导出文件出错：{e}')
            traceback.print_exc()

    def get_pdf_rect(self, page: pdf.Page, rect: SelectedRect) -> pdf.Rect:
        page_width = page.rect.width
        page_height = page.rect.height
        x1 = page_width * rect.x_min
        x2 = page_width * rect.x_max
        y1 = page_height * rect.y_min
        y2 = page_height * rect.y_max
        return pdf.Rect(x1, y1, x2, y2)
