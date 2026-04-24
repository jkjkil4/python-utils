from PySide6.QtWidgets import QApplication, QWidget


def exec_widget(cls: type[QWidget]) -> None:
    app = QApplication()

    w = cls()
    w.show()

    app.exec()
