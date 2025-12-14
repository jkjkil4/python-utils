
import sys
import pymupdf as pdf
from PySide6.QtWidgets import QApplication, QFileDialog


def main() -> None:
    _ = QApplication(sys.argv)

    # 1. 使用 QFileDialog 询问用户打开第一个文件
    file1, _ = QFileDialog.getOpenFileName(None, "Select First PDF", ".", "PDF Files (*.pdf)")
    if not file1:
        return

    # 2. 使用 QFileDialog 询问用户打开第二个文件
    file2, _ = QFileDialog.getOpenFileName(None, "Select Second PDF", ".", "PDF Files (*.pdf)")
    if not file2:
        return

    # 3. 使用 QFileDialog 询问用户输出到哪个文件
    output_file, _ = QFileDialog.getSaveFileName(None, "Save Merged PDF", ".", "PDF Files (*.pdf)")
    if not output_file:
        return

    # 4. 使用 PyMuPDF 合并两个文件并输出
    doc1 = pdf.open(file1)
    doc2 = pdf.open(file2)
    doc1.insert_pdf(doc2)
    doc1.save(output_file)


if __name__ == '__main__':
    main()
