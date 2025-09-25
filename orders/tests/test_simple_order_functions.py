import pytest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from orders.templatetags.file_utils import filesize, filename


class SimpleOrderFunctionsTestCase(TestCase):
    """Простые тесты для основных функций модуля управления заказами"""
    
    def setUp(self):
        # Создаем тестовые файлы
        self.small_file = SimpleUploadedFile(
            "test.xlsx",
            b"x" * 1024,  # 1KB
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        self.pdf_file = SimpleUploadedFile(
            "test.pdf",
            b"%PDF-1.4\nTest PDF content",
            content_type="application/pdf"
        )

    def test_filesize_filter(self):
        """Тест фильтра filesize"""
        result = filesize(self.small_file)
        self.assertEqual(result, "1.0 KB")
        
        # Тест с None
        result = filesize(None)
        self.assertEqual(result, "0 B")

    def test_filename_filter(self):
        """Тест фильтра filename"""
        result = filename(self.small_file)
        self.assertEqual(result, "test.xlsx")
        
        # Тест с None
        result = filename(None)
        self.assertEqual(result, "")

    def test_file_validation_basic(self):
        """Базовый тест валидации файлов"""
        # Проверяем, что файлы созданы корректно
        self.assertTrue(self.small_file.name.endswith('.xlsx'))
        self.assertTrue(self.pdf_file.name.endswith('.pdf'))
        
        # Проверяем размеры
        self.assertEqual(self.small_file.size, 1024)
        self.assertGreater(self.pdf_file.size, 0)

    def test_file_content_types(self):
        """Тест типов содержимого файлов"""
        self.assertEqual(
            self.small_file.content_type,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        self.assertEqual(self.pdf_file.content_type, "application/pdf")

    def test_file_operations(self):
        """Тест операций с файлами"""
        # Чтение файла
        self.small_file.seek(0)
        content = self.small_file.read()
        self.assertEqual(len(content), 1024)
        
        # Возврат указателя в начало
        self.small_file.seek(0)
        self.assertEqual(self.small_file.tell(), 0)

    def test_filesize_edge_cases(self):
        """Тест граничных случаев filesize"""
        # Пустой файл
        empty_file = SimpleUploadedFile("empty.txt", b"", content_type="text/plain")
        result = filesize(empty_file)
        self.assertEqual(result, "0 B")
        
        # Файл размером ровно 1 байт
        one_byte_file = SimpleUploadedFile("one.txt", b"x", content_type="text/plain")
        result = filesize(one_byte_file)
        self.assertEqual(result, "1 B")

    def test_filename_edge_cases(self):
        """Тест граничных случаев filename"""
        # Файл с путем
        file_with_path = SimpleUploadedFile(
            "path/to/file.xlsx",
            b"content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        result = filename(file_with_path)
        self.assertEqual(result, "file.xlsx")
        
        # Файл без расширения
        file_no_ext = SimpleUploadedFile("file", b"content", content_type="text/plain")
        result = filename(file_no_ext)
        self.assertEqual(result, "file")

    def test_filesize_units(self):
        """Тест различных единиц измерения filesize"""
        # Байты
        bytes_file = SimpleUploadedFile("bytes.txt", b"x" * 500, content_type="text/plain")
        result = filesize(bytes_file)
        self.assertEqual(result, "500 B")
        
        # Килобайты
        kb_file = SimpleUploadedFile("kb.txt", b"x" * 1024, content_type="text/plain")
        result = filesize(kb_file)
        self.assertEqual(result, "1.0 KB")
        
        # Мегабайты
        mb_file = SimpleUploadedFile("mb.txt", b"x" * (1024 * 1024), content_type="text/plain")
        result = filesize(mb_file)
        self.assertEqual(result, "1.0 MB")

    def test_filename_unicode(self):
        """Тест обработки Unicode имен файлов"""
        unicode_file = SimpleUploadedFile(
            "файл-заказа.xlsx",
            b"content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        result = filename(unicode_file)
        self.assertEqual(result, "файл-заказа.xlsx")

    def test_filename_with_spaces(self):
        """Тест обработки имен файлов с пробелами"""
        spaced_file = SimpleUploadedFile(
            "file with spaces.txt",
            b"content",
            content_type="text/plain"
        )
        result = filename(spaced_file)
        self.assertEqual(result, "file with spaces.txt")


@pytest.mark.django_db
class SimpleOrderFunctionsPytestTestCase:
    """Простые тесты с использованием pytest"""
    
    def test_filesize_formatting_pytest(self):
        """Тест форматирования размера файла с pytest"""
        small_file = SimpleUploadedFile(
            "test.xlsx",
            b"x" * 1024,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        result = filesize(small_file)
        assert result == "1.0 KB"
        
        # Тест с None
        result = filesize(None)
        assert result == "0 B"

    def test_filename_extraction_pytest(self):
        """Тест извлечения имени файла с pytest"""
        file = SimpleUploadedFile(
            "test.xlsx",
            b"content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        result = filename(file)
        assert result == "test.xlsx"
        
        # Тест с None
        result = filename(None)
        assert result == ""

    def test_file_validation_pytest(self):
        """Тест валидации файлов с pytest"""
        excel_file = SimpleUploadedFile(
            "order.xlsx",
            b"PK\x03\x04" + b"x" * 100,  # Минимальная Excel сигнатура
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        pdf_file = SimpleUploadedFile(
            "invoice.pdf",
            b"%PDF-1.4\n" + b"x" * 100,  # Минимальная PDF сигнатура
            content_type="application/pdf"
        )
        
        # Проверяем, что файлы созданы корректно
        assert excel_file.name.endswith('.xlsx')
        assert pdf_file.name.endswith('.pdf')
        assert excel_file.size > 0
        assert pdf_file.size > 0

    def test_filesize_units_pytest(self):
        """Тест различных единиц измерения с pytest"""
        # Байты
        bytes_file = SimpleUploadedFile("bytes.txt", b"x" * 500, content_type="text/plain")
        result = filesize(bytes_file)
        assert result == "500 B"
        
        # Килобайты
        kb_file = SimpleUploadedFile("kb.txt", b"x" * 1024, content_type="text/plain")
        result = filesize(kb_file)
        assert result == "1.0 KB"
        
        # Мегабайты
        mb_file = SimpleUploadedFile("mb.txt", b"x" * (1024 * 1024), content_type="text/plain")
        result = filesize(mb_file)
        assert result == "1.0 MB"

    def test_filename_edge_cases_pytest(self):
        """Тест граничных случаев для filename с pytest"""
        # Файл с путем
        file_with_path = SimpleUploadedFile(
            "path/to/file.xlsx",
            b"content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        result = filename(file_with_path)
        assert result == "file.xlsx"
        
        # Файл без расширения
        file_no_ext = SimpleUploadedFile("file", b"content", content_type="text/plain")
        result = filename(file_no_ext)
        assert result == "file"
