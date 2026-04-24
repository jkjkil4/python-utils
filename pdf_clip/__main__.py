import sys

sys.path.append('.')

from PySide6.QtWidgets import QApplication

from pdf_clip.main_window import MainWindow


def main():
    app = QApplication()

    w = MainWindow()
    w.show()

    app.exec()


if __name__ == '__main__':
    main()
