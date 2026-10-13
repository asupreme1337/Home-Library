import ast
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from models import Book, CSV_HEADER, Entity, Library, PairMap, ROOT, Session, TIME_FORMAT


class ModelTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "книги.csv"
        self.book = Book("Алые паруса", "Александр Грин", "Повесть", 1923, 96, True, "книга1")

    def test_abstract_class_and_special_methods(self):
        with self.assertRaises(TypeError):
            Entity()
        objects = (self.book, PairMap(((self.book.id, self.book),)),
                   Library(self.path, (self.book,)), Session("Алексей"))
        for obj in objects:
            with self.subTest(класс=type(obj).__name__):
                self.assertIsInstance(obj, Entity)
                self.assertTrue(str(obj))
                self.assertTrue(repr(obj))
                self.assertEqual(obj, obj)
                self.assertLessEqual(obj, obj)
                self.assertIs(obj.__eq__(object()), NotImplemented)
                self.assertIs(obj.__lt__(object()), NotImplemented)
                names = [name for name in vars(type(obj)) if name.startswith("__") and callable(getattr(type(obj), name))]
                self.assertGreaterEqual(len(names), 6)

    def test_setters_validate_data(self):
        invalid = (("title", " "), ("author", ""), ("genre", ""), ("id", ""),
                   ("year", datetime.now().year + 1), ("year", True), ("year", 0),
                   ("pages", -1), ("pages", 1.5), ("read", "Да"), ("title", "Книга\nдругая"))
        for name, value in invalid:
            with self.subTest(поле=name, значение=value), self.assertRaises(ValueError):
                setattr(self.book, name, value)
        with self.assertRaises(ValueError):
            Session("Имя|другое")
        with self.assertRaises(ValueError):
            Session("Алексей\tДенисович")
        session = Session("Алексей")
        with self.assertRaises(ValueError):
            session.time_out = session.time_in - timedelta(seconds=1)

    def test_book_order_and_roundtrip(self):
        other = Book("Ярмарка", "Автор", "Роман", 2000, 100)
        self.assertLess(self.book, other)
        self.assertEqual(self.book, Book.from_row(self.book.to_row()))
        with self.assertRaises(TypeError):
            _ = self.book < 1

    def test_mapping_and_defensive_copies(self):
        mapping = PairMap()
        mapping[self.book.id] = self.book
        self.assertEqual(len(mapping), 1)
        changed = mapping[self.book.id]
        changed.title = "Другое название"
        self.assertNotEqual(mapping[self.book.id], changed)
        mapping[changed.id] = changed
        self.assertEqual(mapping[changed.id], changed)
        self.assertEqual(mapping, PairMap(mapping.pairs))
        with self.assertRaises(ValueError):
            mapping["другой код"] = changed
        with self.assertRaises(ValueError):
            mapping.pairs = ((changed.id, changed), (changed.id, changed))
        self.assertEqual(len(mapping), 1)
        mapping.remove(changed.id)
        with self.assertRaises(KeyError):
            mapping[changed.id]

    def test_first_run_persistence_and_empty_library(self):
        library = Library.load(self.path)
        self.assertGreaterEqual(len(library), 10)
        self.assertTrue(self.path.exists())
        self.assertEqual(library, Library.load(self.path))
        for book in library.books:
            library.delete(book.id)
        self.assertEqual(len(Library.load(self.path)), 0)

    def test_csv_unicode_quotes_and_crud(self):
        library = Library(self.path)
        self.book.title = 'Книга, "цитата" и буква ё'
        library.add(self.book)
        original_id = self.book.id
        changed = library.get(original_id)
        changed.pages = 200
        library.update(changed)
        self.assertEqual(Library.load(self.path).get(original_id).pages, 200)
        self.assertEqual(library.get(original_id).title, self.book.title)
        library.delete(original_id)
        library.add(Book("Новая", "Автор", "Роман", 2001, 25))
        self.assertNotEqual(library.books[0].id, original_id)
        duplicate = library.books[0].copy()
        with self.assertRaises(ValueError):
            library.add(duplicate)

    def test_combined_filters_and_numeric_sort(self):
        a = Book("Альфа", "Автор", "Роман", 2000, 100, True)
        b = Book("Бета", "Автор", "Роман", 1990, 20, False)
        c = Book("Гамма", "Другой", "Повесть", 2010, 9, True)
        library = Library(self.path, (a, b, c))
        self.assertEqual(library.find(" АВТОР ", "Роман", True), [a])
        self.assertEqual(library.find(order=2), [c, b, a])
        self.assertEqual(library.find(order=1), [b, a, c])
        self.assertEqual(library.find(order=2, descending=True), [a, b, c])
        self.assertEqual(library.find("ничего"), [])
        book = library.books[0]
        book.id = "новый код"
        self.assertEqual(library.get(a.id), a)

    def test_bad_file_is_not_overwritten(self):
        for contents in ("Неправильный файл\n", ",".join(CSV_HEADER) + "\n1,Книга\n",
                         ",".join(CSV_HEADER) + "\n1,Книга,Автор,Жанр,2000,10,Возможно\n"):
            self.path.write_text(contents, encoding="utf-8")
            with self.assertRaises(ValueError):
                Library.load(self.path)
            self.assertEqual(self.path.read_text(encoding="utf-8"), contents)

    def test_failed_write_preserves_memory_and_file(self):
        library = Library(self.path, (self.book,))
        library.save()
        before = self.path.read_bytes()
        changed = self.book.copy()
        changed.title = "Изменено"
        with patch("models.os.replace", side_effect=PermissionError("Запись запрещена")):
            with self.assertRaises(PermissionError):
                library.update(changed)
        self.assertEqual(library.get(self.book.id), self.book)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_report_format_unique_paths_and_one_file_per_session(self):
        session = Session("Алексей Денисович")
        session.time_in = datetime(2026, 10, 13, 9, 0, 0)
        reports = self.path.parent / "отчёты"
        path = session.save_report(reports)
        self.assertEqual(path, session.save_report(reports))
        lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 5)
        self.assertEqual(len(set(len(line) for line in lines)), 1)
        self.assertIn("login", lines[1])
        self.assertIn("time_in", lines[1])
        self.assertIn("time_out", lines[1])
        values = [part.strip() for part in lines[3].split("|")[1:-1]]
        self.assertEqual(values[0], session.login)
        self.assertEqual(datetime.strptime(values[1], TIME_FORMAT), session.time_in)
        self.assertEqual(values[2], session.time_out.strftime(TIME_FORMAT))
        other = Session("Алексей Денисович")
        self.assertNotEqual(other.save_report(reports), path)
        self.assertEqual(len(list(reports.glob("*.txt"))), 2)

    def test_report_can_be_retried_after_error(self):
        session = Session("Алексей")
        with patch.object(Path, "open", side_effect=PermissionError("Запись запрещена")):
            with self.assertRaises(PermissionError):
                session.save_report(self.path.parent)
        self.assertIsNone(session.report_path)
        self.assertTrue(session.save_report(self.path.parent).exists())

    def test_no_dicts_or_free_functions_in_application(self):
        for name in ("models.py", "widgets.py", "windows.py", "main.py"):
            tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
            with self.subTest(файл=name):
                self.assertFalse(any(isinstance(node, (ast.Dict, ast.DictComp, ast.Lambda)) for node in ast.walk(tree)))
                self.assertFalse(any(isinstance(node, ast.FunctionDef) for node in tree.body))
                self.assertFalse(any(isinstance(node, ast.Name) and node.id in
                                     ("dict", "defaultdict", "Counter", "DictReader", "DictWriter")
                                     for node in ast.walk(tree)))


if __name__ == "__main__":
    unittest.main()
