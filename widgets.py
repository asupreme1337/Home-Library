from datetime import datetime

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QGroupBox,
    QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)


class AppDialog(QDialog):
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumWidth(460)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.body = QVBoxLayout(self)
        self.body.setContentsMargins(24, 24, 24, 24)
        self.body.setSpacing(16)

    @staticmethod
    def message(parent, title, text, error=False):
        box = QMessageBox(parent)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Warning if error else QMessageBox.Icon.Information)
        box.addButton("Понятно", QMessageBox.ButtonRole.AcceptRole)
        box.exec()

    @staticmethod
    def confirm(parent, title, text):
        box = QMessageBox(parent)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Question)
        remove = box.addButton("Удалить", QMessageBox.ButtonRole.DestructiveRole)
        cancel = box.addButton("Отмена", QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel)
        box.setEscapeButton(cancel)
        box.exec()
        return box.clickedButton() is remove


class TitleLabel(QLabel):
    def __init__(self, text, large=False):
        super().__init__(text)
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setWordWrap(True)
        self.setObjectName("heading" if large else "caption")


class TextField(QLineEdit):
    def __init__(self, placeholder="", limit=200):
        super().__init__()
        self.setPlaceholderText(placeholder)
        self.setMaxLength(limit)
        self.setClearButtonEnabled(True)
        self.setMinimumHeight(36)

    def value(self):
        return self.text().strip()


class ActionButton(QPushButton):
    def __init__(self, text, primary=False):
        super().__init__(text)
        self.setMinimumHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("primary" if primary else "action")
        self.setAutoDefault(False)


class ChoiceField(QComboBox):
    def __init__(self, choices=()):
        super().__init__()
        self.addItems(choices)
        self.setMinimumHeight(36)
        self.setMinimumContentsLength(14)
        self.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)


class NumberField(QSpinBox):
    def __init__(self, year=False):
        super().__init__()
        self.setRange(1, datetime.now().year if year else 2147483647)
        self.setValue(datetime.now().year if year else 100)
        self.setMinimumHeight(36)
        self.setAccelerated(True)


class ReadCheckBox(QCheckBox):
    def __init__(self, text="Книга прочитана"):
        super().__init__(text)
        self.setMinimumHeight(30)
        self.setCursor(Qt.CursorShape.PointingHandCursor)


class FormGroup(QGroupBox):
    def __init__(self, title):
        super().__init__(title)
        self.setFlat(False)
        self.setMinimumWidth(200)


class BookTable(QTableWidget):
    def __init__(self):
        super().__init__(0, 6)
        self.setHorizontalHeaderLabels(("Название", "Автор", "Жанр", "Год", "Страниц", "Прочитано"))
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setAlternatingRowColors(True)
        self.setWordWrap(False)
        self.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.setShowGrid(False)
        self.verticalHeader().hide()
        self.verticalHeader().setDefaultSectionSize(42)
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for index in range(2, 6):
            header.setSectionResizeMode(index, QHeaderView.ResizeMode.ResizeToContents)
        header.setMinimumSectionSize(65)
        self.setMinimumHeight(180)

    def selected_id(self):
        if not self.selectionModel().hasSelection():
            return None
        item = self.item(self.currentRow(), 0)
        return None if item is None else item.data(Qt.ItemDataRole.UserRole)

    def fill(self, books, selected_id=None):
        self.blockSignals(True)
        self.clearContents()
        self.setRowCount(len(books))
        selected_row = -1
        for row, book in enumerate(books):
            values = (book.title, book.author, book.genre, str(book.year), str(book.pages),
                      "Да" if book.read else "Нет")
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, book.id)
                if column >= 3:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.setItem(row, column, item)
            if book.id == selected_id:
                selected_row = row
        if selected_row >= 0:
            self.selectRow(selected_row)
        else:
            self.setCurrentCell(-1, -1)
            self.clearSelection()
        self.blockSignals(False)
