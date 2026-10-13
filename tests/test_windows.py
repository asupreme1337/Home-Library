import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PyQt6.QtCore import QTimer, Qt
from PyQt6.QtGui import QCloseEvent, QFont, QFontDatabase
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

from main import STYLE
from models import Book, Library, ROOT, Session
from widgets import ActionButton, AppDialog
from windows import BookDialog, LibraryWindow, LoginDialog


class WindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        cls.app = QApplication.instance() or QApplication([])
        cls.app.styleHints().setColorScheme(Qt.ColorScheme.Light)
        cls.app.setQuitOnLastWindowClosed(False)
        # Плагин offscreen не подгружает системные шрифты Windows самостоятельно.
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for name in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            if (fonts / name).exists():
                QFontDatabase.addApplicationFont(str(fonts / name))
        cls.app.setFont(QFont("Segoe UI", 10))
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(STYLE)

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "книги.csv"
        self.reports = Path(self.folder.name) / "reports"
        self.library = Library.load(self.path)
        self.window = LibraryWindow(self.library, Session("Алексей"), self.reports)
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()

    def accept_new_book(self):
        dialog = self.app.activeModalWidget()
        dialog.title.setText('Тестовая книга, "с запятой"')
        dialog.author.setText("Тестовый автор")
        dialog.genre.setCurrentText("Новый жанр")
        dialog.pages.setValue(37)
        dialog.accept()

    def accept_edited_book(self):
        dialog = self.app.activeModalWidget()
        dialog.title.setText("Изменено после сортировки")
        dialog.pages.setValue(75)
        dialog.accept()

    def test_login_validation_and_cancel(self):
        login = LoginDialog()
        with patch.object(AppDialog, "message") as message:
            login.accept()
            message.assert_called_once()
        self.assertIsNone(login.session)
        login.reject()
        self.assertEqual(login.result(), AppDialog.DialogCode.Rejected)
        login.login.setText("Алексей")
        login.accept()
        self.assertIsInstance(login.session, Session)
        self.assertEqual(login.result(), AppDialog.DialogCode.Accepted)

    def test_add_edit_delete_after_sorting(self):
        QTimer.singleShot(0, self.accept_new_book)
        self.window.add_book()
        self.assertEqual(len(self.library), 13)
        book_id = self.window.table.selected_id()
        self.assertEqual(self.library.get(book_id).pages, 37)
        self.window.order.setCurrentIndex(2)
        self.window.descending.setChecked(True)
        self.assertEqual(self.window.table.selected_id(), book_id)
        QTimer.singleShot(0, self.accept_edited_book)
        self.window.edit_book()
        self.assertEqual(self.library.get(book_id).title, "Изменено после сортировки")
        self.assertEqual(Library.load(self.path).get(book_id).pages, 75)
        with patch.object(AppDialog, "confirm", return_value=True):
            self.window.delete_book()
        self.assertEqual(len(self.library), 12)
        with self.assertRaises(KeyError):
            self.library.get(book_id)
        self.assertIsNone(self.window.table.selected_id())
        self.assertFalse(self.window.delete_button.isEnabled())

    def test_cancelled_delete_does_not_change_catalog(self):
        self.window.table.selectRow(0)
        book_id = self.window.table.selected_id()
        with patch.object(AppDialog, "confirm", return_value=False):
            self.window.delete_book()
        self.assertEqual(self.library.get(book_id).id, book_id)
        self.assertEqual(len(self.library), 12)

    def test_toggle_read_and_combined_filters(self):
        self.window.search.setText("СТРУГАЦКИЕ")
        self.window.genre.setCurrentText("Фантастика")
        self.window.read_filter.setCurrentIndex(2)
        self.assertEqual(self.window.table.rowCount(), 2)
        self.window.table.selectRow(0)
        book_id = self.window.table.selected_id()
        QTest.mouseClick(self.window.read_button, Qt.MouseButton.LeftButton)
        self.assertTrue(self.library.get(book_id).read)
        self.assertEqual(self.window.table.rowCount(), 1)
        self.assertIsNone(self.window.table.selected_id())
        self.window.search.setText("Ничего не найдено")
        self.assertEqual(self.window.table.rowCount(), 0)
        self.assertTrue(self.window.empty.isVisible())
        self.assertFalse(self.window.edit_button.isEnabled())
        self.window.edit_book()
        self.window.toggle_read()
        self.window.delete_book()

    def test_save_failure_displays_russian_message(self):
        self.window.table.selectRow(0)
        before = self.library.get(self.window.table.selected_id())
        with patch.object(Library, "write_books", side_effect=PermissionError("Запись запрещена")):
            with patch.object(AppDialog, "message") as message:
                self.window.toggle_read()
                message.assert_called_once()
                self.assertIn("Предыдущие данные сохранены", message.call_args.args[2])
        self.assertEqual(self.library.get(before.id), before)

    def test_close_failure_keeps_window_open_and_allows_retry(self):
        with patch.object(Session, "save_report", side_effect=PermissionError("Запись запрещена")):
            with patch.object(AppDialog, "message") as message:
                self.assertFalse(self.window.close())
                self.assertTrue(self.window.isVisible())
                message.assert_called_once()
                self.assertIn("повторите закрытие", message.call_args.args[2])
        self.assertTrue(self.window.close())
        self.assertEqual(len(list(self.reports.glob("*.txt"))), 1)
        self.window.close()
        self.assertEqual(len(list(self.reports.glob("*.txt"))), 1)

    def test_exit_button_and_close_event_save_reports(self):
        for button in self.window.findChildren(ActionButton):
            if button.text() == "Выйти":
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
                break
        self.assertFalse(self.window.isVisible())
        self.assertTrue(self.window.session.report_path.exists())
        window = LibraryWindow(self.library, Session("Другой пользователь"), self.reports)
        event = QCloseEvent()
        window.closeEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertTrue(window.session.report_path.exists())
        window.deleteLater()
        self.assertEqual(len(list(self.reports.glob("*.txt"))), 2)

    def test_book_dialog_validates_and_rejects(self):
        dialog = BookDialog(self.library.genres(), parent=self.window)
        with patch.object(AppDialog, "message") as message:
            dialog.accept()
            message.assert_called_once()
        self.assertIsNone(dialog.book)
        dialog.reject()
        self.assertEqual(dialog.result(), AppDialog.DialogCode.Rejected)

    def test_render_window_and_dialogs_at_different_sizes(self):
        output = ROOT / "tmp" / "previews"
        output.mkdir(parents=True, exist_ok=True)
        self.assertTrue(self.window.grab().save(str(output / "library.png")))
        self.window.resize(900, 620)
        self.app.processEvents()
        self.assertTrue(self.window.grab().save(str(output / "library-small.png")))
        self.assertGreater(self.window.table.height(), 150)
        book = self.library.books[0]
        book.title = "Очень длинное русское название книги для проверки отображения " * 2
        self.library.update(book)
        self.window.refresh()
        for row in range(self.window.table.rowCount()):
            item = self.window.table.item(row, 0)
            if item.data(Qt.ItemDataRole.UserRole) == book.id:
                self.assertEqual(item.toolTip(), book.title)
        login = LoginDialog()
        login.show()
        self.app.processEvents()
        self.assertTrue(login.grab().save(str(output / "login.png")))
        login.close()
        editor = BookDialog(self.library.genres(), self.library.books[0], self.window)
        editor.show()
        self.app.processEvents()
        self.assertTrue(editor.grab().save(str(output / "book-dialog.png")))
        editor.close()


if __name__ == "__main__":
    unittest.main()
