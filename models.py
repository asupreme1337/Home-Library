import csv
import os
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from uuid import uuid4


ROOT = Path(__file__).resolve().parent
TIME_FORMAT = "%d.%m.%Y %H:%M:%S"
CSV_HEADER = ("Код", "Название", "Автор", "Жанр", "Год", "Страниц", "Прочитано")


class Entity(ABC):
    @abstractmethod
    def describe(self):
        raise NotImplementedError


class Book(Entity):
    def __init__(self, title, author, genre, year, pages, read=False, book_id=None):
        self.id = uuid4().hex if book_id is None else book_id
        self.title = title
        self.author = author
        self.genre = genre
        self.year = year
        self.pages = pages
        self.read = read

    @staticmethod
    def clean_text(value, label, limit=200):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Поле «{label}» не должно быть пустым.")
        if len(value.strip()) > limit or any(not c.isprintable() for c in value):
            raise ValueError(f"Поле «{label}»: максимум {limit} символов, без переносов строк.")
        return value.strip()

    @property
    def id(self):
        return self._id

    @id.setter
    def id(self, value):
        self._id = self.clean_text(value, "Код", 100)

    @property
    def title(self):
        return self._title

    @title.setter
    def title(self, value):
        self._title = self.clean_text(value, "Название")

    @property
    def author(self):
        return self._author

    @author.setter
    def author(self, value):
        self._author = self.clean_text(value, "Автор")

    @property
    def genre(self):
        return self._genre

    @genre.setter
    def genre(self, value):
        self._genre = self.clean_text(value, "Жанр", 80)

    @property
    def year(self):
        return self._year

    @year.setter
    def year(self, value):
        if type(value) is not int or not 1 <= value <= datetime.now().year:
            raise ValueError("Год должен быть целым числом от 1 до текущего года.")
        self._year = value

    @property
    def pages(self):
        return self._pages

    @pages.setter
    def pages(self, value):
        if type(value) is not int or not 1 <= value <= 2147483647:
            raise ValueError("Количество страниц должно быть целым числом от 1 до 2147483647.")
        self._pages = value

    @property
    def read(self):
        return self._read

    @read.setter
    def read(self, value):
        if type(value) is not bool:
            raise ValueError("Отметка о прочтении должна иметь значение Да или Нет.")
        self._read = value

    def copy(self):
        return Book(self.title, self.author, self.genre, self.year, self.pages, self.read, self.id)

    def to_row(self):
        return [self.id, self.title, self.author, self.genre, str(self.year), str(self.pages),
                "Да" if self.read else "Нет"]

    @staticmethod
    def from_row(row):
        if len(row) != len(CSV_HEADER) or row[6] not in ("Да", "Нет"):
            raise ValueError("Неверное число столбцов или отметка о прочтении.")
        return Book(row[1], row[2], row[3], int(row[4]), int(row[5]), row[6] == "Да", row[0])

    def comparison_key(self):
        return (self.title.casefold(), self.title, self.author, self.year, self.pages,
                self.genre, self.read, self.id)

    def describe(self):
        return f"{self.author}. {self.title} ({self.year}), {self.pages} стр."

    def __eq__(self, other):
        if not isinstance(other, Book):
            return NotImplemented
        return self.comparison_key() == other.comparison_key()

    def __lt__(self, other):
        if not isinstance(other, Book):
            return NotImplemented
        return self.comparison_key() < other.comparison_key()

    def __le__(self, other):
        if not isinstance(other, Book):
            return NotImplemented
        return self == other or self < other

    def __repr__(self):
        return f"Book({self.title!r}, {self.author!r}, код={self.id!r})"

    def __str__(self):
        return self.describe()


class PairMap(Entity):
    """Небольшой маппинг книг: внутри обычный список пар (код, книга)."""

    def __init__(self, pairs=()):
        self.pairs = pairs

    @property
    def pairs(self):
        return tuple((key, value.copy()) for key, value in self._pairs)

    @pairs.setter
    def pairs(self, value):
        result = []
        keys = []
        for key, book in value:
            self.check_pair(key, book)
            if key in keys:
                raise ValueError("Коды книг не должны повторяться.")
            keys.append(key)
            result.append((key, book.copy()))
        self._pairs = result

    @staticmethod
    def check_pair(key, book):
        if not isinstance(book, Book) or key != book.id:
            raise ValueError("Ключ маппинга должен совпадать с кодом книги.")

    def remove(self, key):
        for index, pair in enumerate(self._pairs):
            if pair[0] == key:
                self._pairs.pop(index)
                return
        raise KeyError("Книга не найдена.")

    def values(self):
        return tuple(book.copy() for key, book in self._pairs)

    def describe(self):
        return f"Маппинг: {len(self)} книг"

    def __len__(self):
        return len(self._pairs)

    def __getitem__(self, key):
        for stored_key, book in self._pairs:
            if stored_key == key:
                return book.copy()
        raise KeyError("Книга не найдена.")

    def __setitem__(self, key, book):
        self.check_pair(key, book)
        for index, pair in enumerate(self._pairs):
            if pair[0] == key:
                self._pairs[index] = (key, book.copy())
                return
        self._pairs.append((key, book.copy()))

    def __eq__(self, other):
        if not isinstance(other, PairMap):
            return NotImplemented
        return sorted(self._pairs) == sorted(other._pairs)

    def __lt__(self, other):
        if not isinstance(other, PairMap):
            return NotImplemented
        return sorted(self._pairs) < sorted(other._pairs)

    def __le__(self, other):
        if not isinstance(other, PairMap):
            return NotImplemented
        return self == other or self < other

    def __repr__(self):
        return f"PairMap({self.pairs!r})"

    def __str__(self):
        return self.describe()


class Library(Entity):
    def __init__(self, path=ROOT / "data" / "books.csv", books=()):
        self.path = path
        self.books = books

    @property
    def path(self):
        return self._path

    @path.setter
    def path(self, value):
        if not isinstance(value, (str, Path)) or not str(value).strip():
            raise ValueError("Нужно указать путь к файлу каталога.")
        self._path = Path(value).resolve()

    @property
    def books(self):
        return self._books.values()

    @books.setter
    def books(self, value):
        self._books = PairMap((book.id, book) for book in value)

    @classmethod
    def load(cls, path=ROOT / "data" / "books.csv", example=ROOT / "data" / "books_example.csv"):
        library = cls(path)
        source = library.path if library.path.exists() else Path(example)
        books = []
        try:
            with source.open(encoding="utf-8-sig", newline="") as file:
                reader = csv.reader(file, strict=True)
                if tuple(next(reader, [])) != CSV_HEADER:
                    raise ValueError("Неверные заголовки CSV.")
                for row in reader:
                    try:
                        books.append(Book.from_row(row))
                    except (ValueError, TypeError) as error:
                        raise ValueError(f"Строка {reader.line_num}: {error}") from error
            library.books = books
        except (csv.Error, UnicodeError) as error:
            raise ValueError(f"Не удалось прочитать каталог: {error}") from error
        if source != library.path:
            library.save()
        return library

    def save(self):
        self.write_books(self.books)

    def write_books(self, books):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="",
                                             dir=self.path.parent, delete=False) as file:
                temporary = Path(file.name)
                writer = csv.writer(file)
                writer.writerow(CSV_HEADER)
                for book in books:
                    writer.writerow(book.to_row())
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self.path)
        finally:
            if temporary is not None and temporary.exists():
                temporary.unlink()

    def commit(self, books):
        candidate = PairMap((book.id, book) for book in books)
        self.write_books(candidate.values())
        self._books = candidate

    def get(self, book_id):
        return self._books[book_id]

    def add(self, book):
        if any(item.id == book.id for item in self):
            raise ValueError("Книга с таким кодом уже есть.")
        self.commit(self.books + (book,))

    def update(self, book):
        self.get(book.id)
        self.commit(tuple(book if item.id == book.id else item for item in self))

    def delete(self, book_id):
        self.get(book_id)
        self.commit(tuple(book for book in self if book.id != book_id))

    def genres(self):
        return sorted(set(book.genre for book in self), key=str.casefold)

    @staticmethod
    def title_key(book):
        return (book.title.casefold(), book.author.casefold(), book.id)

    @staticmethod
    def year_key(book):
        return (book.year, book.title.casefold(), book.id)

    @staticmethod
    def pages_key(book):
        return (book.pages, book.title.casefold(), book.id)

    def find(self, query="", genre=None, read=None, order=0, descending=False):
        query = query.strip().casefold()
        found = []
        for book in self:
            if query and query not in book.title.casefold() and query not in book.author.casefold():
                continue
            if genre is not None and book.genre != genre:
                continue
            if read is not None and book.read != read:
                continue
            found.append(book)
        keys = (self.title_key, self.year_key, self.pages_key)
        return sorted(found, key=keys[order], reverse=descending)

    def describe(self):
        return f"Библиотека: {len(self)} книг"

    def __len__(self):
        return len(self._books)

    def __iter__(self):
        return iter(self.books)

    def __eq__(self, other):
        if not isinstance(other, Library):
            return NotImplemented
        return sorted(self.books) == sorted(other.books)

    def __lt__(self, other):
        if not isinstance(other, Library):
            return NotImplemented
        return sorted(self.books) < sorted(other.books)

    def __le__(self, other):
        if not isinstance(other, Library):
            return NotImplemented
        return self == other or self < other

    def __repr__(self):
        return f"Library(путь={str(self.path)!r}, книг={len(self)})"

    def __str__(self):
        return self.describe()


class Session(Entity):
    def __init__(self, login):
        self.login = login
        self.time_in = datetime.now()
        self.time_out = None
        self.report_path = None

    @property
    def login(self):
        return self._login

    @login.setter
    def login(self, value):
        value = Book.clean_text(value, "Имя пользователя", 80)
        if "|" in value:
            raise ValueError("Имя пользователя не должно содержать символ |.")
        self._login = value

    @property
    def time_in(self):
        return self._time_in

    @time_in.setter
    def time_in(self, value):
        if not isinstance(value, datetime) or value.tzinfo is not None:
            raise ValueError("Время входа должно быть локальной датой и временем.")
        if getattr(self, "_time_out", None) is not None and value > self.time_out:
            raise ValueError("Время входа не может быть позже выхода.")
        self._time_in = value

    @property
    def time_out(self):
        return self._time_out

    @time_out.setter
    def time_out(self, value):
        if value is not None:
            if not isinstance(value, datetime) or value.tzinfo is not None:
                raise ValueError("Время выхода должно быть локальной датой и временем.")
            if value < self.time_in:
                raise ValueError("Время выхода не может быть раньше входа.")
        self._time_out = value

    @property
    def report_path(self):
        return self._report_path

    @report_path.setter
    def report_path(self, value):
        if value is not None and not isinstance(value, (str, Path)):
            raise ValueError("Неверный путь к отчёту.")
        self._report_path = None if value is None else Path(value)

    def report_text(self):
        if self.time_out is None:
            raise ValueError("Сеанс ещё не завершён.")
        rows = (("login", "time_in", "time_out"),
                (self.login, self.time_in.strftime(TIME_FORMAT), self.time_out.strftime(TIME_FORMAT)))
        widths = [max(len(row[index]) for row in rows) for index in range(3)]
        lines = []
        for row in rows:
            lines.append("| " + " | ".join(row[i].ljust(widths[i]) for i in range(3)) + " |")
        border = "+" + "-" * (len(lines[0]) - 2) + "+"
        separator = "|" + "|".join("-" * (width + 2) for width in widths) + "|"
        return "\n".join((border, lines[0], separator, lines[1], border)) + "\n"

    def save_report(self, folder=ROOT / "reports"):
        if self.report_path is not None:
            return self.report_path
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        self.time_out = max(datetime.now(), self.time_in)
        path = folder / f"сеанс_{self.time_in:%Y%m%d_%H%M%S}_{uuid4().hex}.txt"
        created = False
        try:
            with path.open("x", encoding="utf-8", newline="\n") as file:
                created = True
                file.write(self.report_text())
                file.flush()
                os.fsync(file.fileno())
        except OSError:
            if created:
                path.unlink(missing_ok=True)
            raise
        self.report_path = path
        return path

    def comparison_key(self):
        return (self.time_in, self.login, self.time_out or datetime.min)

    def describe(self):
        return f"{self.login}, вход: {self.time_in.strftime(TIME_FORMAT)}"

    def __eq__(self, other):
        if not isinstance(other, Session):
            return NotImplemented
        return self.comparison_key() == other.comparison_key()

    def __lt__(self, other):
        if not isinstance(other, Session):
            return NotImplemented
        return self.comparison_key() < other.comparison_key()

    def __le__(self, other):
        if not isinstance(other, Session):
            return NotImplemented
        return self == other or self < other

    def __repr__(self):
        return f"Session({self.login!r}, вход={self.time_in!r})"

    def __str__(self):
        return self.describe()
