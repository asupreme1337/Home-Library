import sys

from PyQt6.QtCore import QLibraryInfo, QLocale, Qt, QTranslator
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QApplication

from models import Library
from widgets import AppDialog
from windows import LibraryWindow, LoginDialog


STYLE = """
QWidget { font-family: 'Segoe UI'; font-size: 10pt; color: #263540; }
QMainWindow, QDialog { background: #f3f5f7; }
QLabel#heading { font-size: 24pt; font-weight: 600; color: #193c40; }
QLabel#caption { color: #52636e; }
QLineEdit, QComboBox, QSpinBox {
    background: white; border: 1px solid #bdcbd2; border-radius: 5px; padding: 4px 9px;
    selection-background-color: #d0e8e3; selection-color: #183b36;
}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus { border: 1px solid #147d70; }
QPushButton { background: white; border: 1px solid #bdcbd2; border-radius: 5px; padding: 7px 14px; }
QPushButton:hover { background: #e9efef; border-color: #63877f; }
QPushButton:pressed { background: #d8e5e2; }
QPushButton#primary { background: #176f63; border-color: #176f63; color: white; font-weight: 600; }
QPushButton#primary:hover { background: #12594f; }
QPushButton:disabled { color: #8a969f; background: #edf0f2; border-color: #d6dde2; }
QGroupBox { background: white; border: 1px solid #d5dfe5; border-radius: 8px; margin-top: 10px; }
QGroupBox::title { subcontrol-origin: margin; left: 16px; padding: 0 5px; color: #45616a; }
QTableWidget { background: white; alternate-background-color: #f7f9fa; border: 1px solid #d5dfe5;
    border-radius: 6px; selection-background-color: #d0e8e3; selection-color: #193c40; }
QTableWidget::item { padding: 6px; border: 0; }
QTableWidget::item:focus { border: 1px solid #147d70; }
QHeaderView::section { background: #e7edef; color: #39525e; padding: 10px 6px;
    border: 0; border-bottom: 1px solid #d5dfe5; font-weight: 600; }
QStatusBar { background: #e7edef; color: #52636e; }
QToolTip { background: #ffffff; color: #263540; border: 1px solid #bdcbd2; padding: 6px; }
"""


class Application:
    @staticmethod
    def run():
        QLocale.setDefault(QLocale(QLocale.Language.Russian, QLocale.Country.Russia))
        app = QApplication(sys.argv)
        app.styleHints().setColorScheme(Qt.ColorScheme.Light)
        app.setApplicationName("Домашняя библиотека")
        app.setFont(QFont("Segoe UI", 10))
        app.setStyle("Fusion")
        app.setStyleSheet(STYLE)
        translator = QTranslator(app)
        translations = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load("qtbase_ru", translations):
            app.installTranslator(translator)
        app.setQuitOnLastWindowClosed(False)
        try:
            library = Library.load()
        except (OSError, ValueError):
            AppDialog.message(None, "Каталог недоступен", "Не удалось открыть каталог. Проверьте "
                              "файлы data/books.csv и data/books_example.csv и права на папку data. "
                              "Существующий файл не будет заменён демонстрационными данными.", error=True)
            return 1
        login = LoginDialog()
        if login.exec() != AppDialog.DialogCode.Accepted:
            return 0
        window = LibraryWindow(library, login.session)
        window.show()
        app.setQuitOnLastWindowClosed(True)
        return app.exec()


if __name__ == "__main__":
    sys.exit(Application.run())
