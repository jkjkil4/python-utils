import sys

sys.path.append('.')

import os

from PySide6.QtCore import QMargins, Qt
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget
from pdf_clip.components.zoom_area import AbstractNavigatableZoomArea


class Navigator[T: AbstractNavigatableZoomArea](QWidget):
    def __init__(self, view_cls: type[T], parent=None):
        super().__init__(parent)
        self.pages_view = view_cls(self)
        self.page_edit = QLineEdit(self)
        self.page_label = QLabel(self)
        self.page_edit.setFixedWidth(60)
        self.page_edit.setAlignment(Qt.AlignmentFlag.AlignRight)

        self.page_edit.returnPressed.connect(self.goto_page)
        self.pages_view.set_y_margin(100, True)
        self.pages_view.scrolled.connect(self.update_page_display)

        nav_layout = QHBoxLayout()
        nav_layout.setContentsMargins(QMargins())
        nav_layout.addWidget(self.page_edit)
        nav_layout.addWidget(QLabel('/', self))
        nav_layout.addWidget(self.page_label)
        nav_layout.addStretch()

        nav_widget = QWidget()
        nav_widget.setObjectName('nav_widget')
        nav_widget.setLayout(nav_layout)
        nav_widget.setStyleSheet('#nav_widget { background-color: #d0ddff; }')

        layout = QVBoxLayout(self)
        layout.addWidget(nav_widget)
        layout.addWidget(self.pages_view, 1)
        layout.setContentsMargins(QMargins())
        self.setLayout(layout)

    def goto_page(self):
        page_num = int(self.page_edit.text())
        self.pages_view.scroll_to_page(page_num)

    def update_page_display(self):
        current = self.pages_view.current_page_index() + 1
        total = self.pages_view.page_count()
        self.page_edit.setText(str(current))
        self.page_label.setText(str(total))


if __name__ == '__main__':
    from pdf_clip.components.pixmap_pages import PixmapPages
    from utils.qt import exec_widget

    class TestPixmapNavigator(Navigator):
        def __init__(self, parent=None):
            super().__init__(PixmapPages, parent)

            # Load images from ~/Pictures/截图/
            pictures_dir = os.path.expanduser('~/Pictures/截图/')
            image_files = [
                os.path.join(pictures_dir, f)
                for f in os.listdir(pictures_dir)
                if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp', '.gif'))
            ]
            pixmaps = [QPixmap(path) for path in image_files if os.path.isfile(path)]
            self.pages_view.set_pixmaps(pixmaps)

    exec_widget(TestPixmapNavigator)
