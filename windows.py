from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QFormLayout, QHBoxLayout, QMainWindow, QVBoxLayout, QWidget

from models import Book, ROOT, Session
from widgets import (
    ActionButton, AppDialog, BookTable, ChoiceField, FormGroup,
    NumberField, ReadCheckBox, TextField, TitleLabel,
)


class LoginDialog(AppDialog):
    def __init__(self):
        super().__init__("Вход в домашнюю библиотеку")
        self.session = None
        self.body.addWidget(TitleLabel("Домашняя библиотека", large=True))
        self.body.addWidget(TitleLabel("Введите имя пользователя. Оно будет указано в отчёте о сеансе."))
        self.login = TextField("Например, Алексей", 80)
        self.login.setAccessibleName("Имя пользователя")
        self.body.addWidget(self.login)
        buttons = QHBoxLayout()
        cancel = ActionButton("Отмена")
        enter = ActionButton("Войти", primary=True)
        buttons.addWidget(cancel)
        buttons.addWidget(enter)
        self.body.addLayout(buttons)
        cancel.clicked.connect(self.reject)
        enter.clicked.connect(self.accept)
        self.login.returnPressed.connect(self.accept)
        self.login.setFocus()

    def accept(self):
        try:
            self.session = Session(self.login.value())
        except ValueError as error:
            self.message(self, "Проверьте имя", str(error), error=True)
            return
        super().accept()


class BookDialog(AppDialog):
    def __init__(self, genres, book=None, parent=None):
        super().__init__("Добавить книгу" if book is None else "Редактировать книгу", parent)
        self.book = None
        self.book_id = None if book is None else book.id
        self.body.addWidget(TitleLabel(self.windowTitle(), large=True))
        form = QFormLayout()
        form.setSpacing(12)
        self.title = TextField("Название книги")
        self.author = TextField("Имя автора")
        self.genre = ChoiceField(genres)
        self.genre.setEditable(True)
        self.genre.lineEdit().setMaxLength(80)
        self.genre.setCurrentIndex(-1)
        self.genre.lineEdit().setPlaceholderText("Выберите или введите жанр")
        self.year = NumberField(year=True)
        self.pages = NumberField()
        self.read = ReadCheckBox()
        for label, field in (("Название:", self.title), ("Автор:", self.author),
                             ("Жанр:", self.genre), ("Год издания:", self.year),
                             ("Страниц:", self.pages)):
            form.addRow(label, field)
        form.addRow("", self.read)
        self.body.addLayout(form)
        buttons = QHBoxLayout()
        cancel = ActionButton("Отмена")
        save = ActionButton("Сохранить", primary=True)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        self.body.addLayout(buttons)
        cancel.clicked.connect(self.reject)
        save.clicked.connect(self.accept)
        if book is not None:
            self.title.setText(book.title)
            self.author.setText(book.author)
            self.genre.setCurrentText(book.genre)
            self.year.setValue(book.year)
            self.pages.setValue(book.pages)
            self.read.setChecked(book.read)
        self.title.setFocus()

    def accept(self):
        self.year.interpretText()
        self.pages.interpretText()
        try:
            self.book = Book(self.title.value(), self.author.value(), self.genre.currentText(),
                             self.year.value(), self.pages.value(), self.read.isChecked(), self.book_id)
        except ValueError as error:
            self.message(self, "Проверьте данные", str(error), error=True)
            return
        super().accept()


class LibraryWindow(QMainWindow):
    def __init__(self, library, session, reports_folder=ROOT / "reports"):
        super().__init__()
        self.library = library
        self.session = session
        self.reports_folder = reports_folder
        self.setWindowTitle("Домашняя библиотека")
        self.resize(1160, 780)
        self.setMinimumSize(900, 620)
        self.build()
        self.update_genres()
        self.refresh()

    def build(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(28, 24, 28, 20)
        layout.setSpacing(16)
        top = QHBoxLayout()
        titles = QVBoxLayout()
        titles.addWidget(TitleLabel("Домашняя библиотека", large=True))
        titles.addWidget(TitleLabel("Книги, которые хочется прочитать и сохранить"))
        top.addLayout(titles, 1)
        about = ActionButton("О программе")
        about.clicked.connect(self.about)
        top.addWidget(about)
        layout.addLayout(top)
        layout.addWidget(TitleLabel(f"Пользователь: {self.session.login}"))

        filters = FormGroup("Поиск и порядок книг")
        filter_layout = QVBoxLayout(filters)
        filter_layout.setContentsMargins(16, 24, 16, 16)
        filter_layout.setSpacing(12)
        self.search = TextField("Найти по названию или автору")
        self.search.setAccessibleName("Поиск книг")
        filter_layout.addWidget(self.search)
        row = QHBoxLayout()
        self.genre = ChoiceField(("Все жанры",))
        self.genre.setAccessibleName("Фильтр по жанру")
        self.read_filter = ChoiceField(("Все книги", "Прочитанные", "Непрочитанные"))
        self.read_filter.setAccessibleName("Фильтр по прочтению")
        self.order = ChoiceField(("По названию", "По году", "По страницам"))
        self.order.setAccessibleName("Сортировка книг")
        self.descending = ReadCheckBox("По убыванию")
        for field in (self.genre, self.read_filter, self.order):
            row.addWidget(field, 1)
        row.addWidget(self.descending)
        filter_layout.addLayout(row)
        layout.addWidget(filters)

        toolbar = QHBoxLayout()
        add = ActionButton("Добавить книгу", primary=True)
        self.edit_button = ActionButton("Редактировать")
        self.read_button = ActionButton("Отметить прочитанной")
        self.delete_button = ActionButton("Удалить")
        for button in (add, self.edit_button, self.read_button, self.delete_button):
            toolbar.addWidget(button)
        toolbar.addStretch()
        layout.addLayout(toolbar)
        self.table = BookTable()
        layout.addWidget(self.table, 1)
        self.empty = TitleLabel("Книги не найдены. Измените условия поиска или добавьте книгу.")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.empty)
        footer = QHBoxLayout()
        self.summary = TitleLabel("")
        footer.addWidget(self.summary, 1)
        exit_button = ActionButton("Выйти")
        footer.addWidget(exit_button)
        layout.addLayout(footer)
        self.statusBar().showMessage("Изменения сохраняются автоматически")

        self.search.textChanged.connect(self.refresh)
        self.genre.currentIndexChanged.connect(self.refresh)
        self.read_filter.currentIndexChanged.connect(self.refresh)
        self.order.currentIndexChanged.connect(self.refresh)
        self.descending.toggled.connect(self.refresh)
        self.table.itemSelectionChanged.connect(self.update_buttons)
        self.table.itemDoubleClicked.connect(self.edit_book)
        add.clicked.connect(self.add_book)
        self.edit_button.clicked.connect(self.edit_book)
        self.read_button.clicked.connect(self.toggle_read)
        self.delete_button.clicked.connect(self.delete_book)
        exit_button.clicked.connect(self.close)

    def update_genres(self):
        selected = self.genre.currentText() if self.genre.currentIndex() > 0 else None
        self.genre.blockSignals(True)
        self.genre.clear()
        self.genre.addItem("Все жанры")
        self.genre.addItems(self.library.genres())
        if selected is not None:
            index = self.genre.findText(selected)
            self.genre.setCurrentIndex(max(0, index))
        self.genre.blockSignals(False)

    def refresh(self):
        selected = self.table.selected_id()
        genre = self.genre.currentText() if self.genre.currentIndex() > 0 else None
        read = (None, True, False)[self.read_filter.currentIndex()]
        books = self.library.find(self.search.value(), genre, read, self.order.currentIndex(),
                                  self.descending.isChecked())
        self.table.fill(books, selected)
        self.empty.setVisible(not books)
        read_count = sum(book.read for book in books)
        self.summary.setText(f"Показано: {len(books)} из {len(self.library)}  ·  "
                             f"Прочитано среди найденных: {read_count}")
        self.update_buttons()

    def update_buttons(self):
        book_id = self.table.selected_id()
        for button in (self.edit_button, self.read_button, self.delete_button):
            button.setEnabled(book_id is not None)
        if book_id is not None:
            read = self.library.get(book_id).read
            self.read_button.setText("Отметить непрочитанной" if read else "Отметить прочитанной")

    def save_error(self, error):
        if isinstance(error, OSError):
            text = ("Не удалось сохранить каталог. Проверьте права на папку data и свободное место "
                    "на диске. Предыдущие данные сохранены. Повторите операцию.")
        else:
            text = str(error)
        AppDialog.message(self, "Изменения не сохранены", text, error=True)

    def changed(self, book_id=None):
        self.table.clearSelection()
        self.table.setCurrentCell(-1, -1)
        self.update_genres()
        self.refresh()
        if book_id is not None:
            for row in range(self.table.rowCount()):
                if self.table.item(row, 0).data(Qt.ItemDataRole.UserRole) == book_id:
                    self.table.selectRow(row)
                    break
        self.statusBar().showMessage("Изменения сохранены", 4000)

    def add_book(self):
        dialog = BookDialog(self.library.genres(), parent=self)
        if dialog.exec() != AppDialog.DialogCode.Accepted:
            return
        try:
            self.library.add(dialog.book)
        except (OSError, ValueError) as error:
            self.save_error(error)
            return
        self.changed(dialog.book.id)

    def edit_book(self):
        book_id = self.table.selected_id()
        if book_id is None:
            return
        dialog = BookDialog(self.library.genres(), self.library.get(book_id), self)
        if dialog.exec() != AppDialog.DialogCode.Accepted:
            return
        try:
            self.library.update(dialog.book)
        except (OSError, ValueError) as error:
            self.save_error(error)
            return
        self.changed(book_id)

    def toggle_read(self):
        book_id = self.table.selected_id()
        if book_id is None:
            return
        book = self.library.get(book_id)
        book.read = not book.read
        try:
            self.library.update(book)
        except (OSError, ValueError) as error:
            self.save_error(error)
            return
        self.changed(book_id)

    def delete_book(self):
        book_id = self.table.selected_id()
        if book_id is None:
            return
        book = self.library.get(book_id)
        if not AppDialog.confirm(self, "Удалить книгу?", f"Удалить «{book.title}» из библиотеки?"):
            return
        try:
            self.library.delete(book_id)
        except (OSError, ValueError) as error:
            self.save_error(error)
            return
        self.changed()

    def about(self):
        AppDialog.message(self, "О программе", "Домашняя библиотека\n\n"
                          "Учебная работа по дисциплине\n«Объектно-ориентированное программирование»\n\n"
                          "Козырев Алексей Денисович\nГруппа: ОVБИм-206рсоб\n\nPython и PyQt6")

    def closeEvent(self, event):
        try:
            self.session.save_report(self.reports_folder)
        except (OSError, ValueError):
            event.ignore()
            AppDialog.message(self, "Отчёт не сохранён", "Не удалось сохранить отчёт о сеансе. "
                              "Проверьте права на папку reports и свободное место на диске, "
                              "затем повторите закрытие. Приложение остаётся открытым.", error=True)
            return
        event.accept()
