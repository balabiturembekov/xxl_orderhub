import pytest
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from orders.templatetags.file_utils import filesize, filename


class TemplateFiltersTestCase(TestCase):
    """Тесты для template filters"""
    
    def setUp(self):
        # Создаем тестовые файлы разных размеров
        self.small_file = SimpleUploadedFile(
            "small.txt",
            b"x" * 1024,  # 1KB
            content_type="text/plain"
        )
        
        self.medium_file = SimpleUploadedFile(
            "medium.txt",
            b"x" * (1024 * 1024),  # 1MB
            content_type="text/plain"
        )
        
        self.large_file = SimpleUploadedFile(
            "large.txt",
            b"x" * (1024 * 1024 * 1024),  # 1GB
            content_type="text/plain"
        )
        
        self.very_large_file = SimpleUploadedFile(
            "very_large.txt",
            b"x" * (1024 * 1024 * 1024 * 2),  # 2GB
            content_type="text/plain"
        )

    def test_filesize_bytes(self):
        """Тест форматирования размера файла в байтах"""
        # Файл размером 1KB
        result = filesize(self.small_file)
        self.assertEqual(result, "1.0 KB")
        
        # Файл размером 0 байт
        empty_file = SimpleUploadedFile("empty.txt", b"", content_type="text/plain")
        result = filesize(empty_file)
        self.assertEqual(result, "0 B")

    def test_filesize_kilobytes(self):
        """Тест форматирования размера файла в килобайтах"""
        # Файл размером 1MB
        result = filesize(self.medium_file)
        self.assertEqual(result, "1.0 MB")

    def test_filesize_gigabytes(self):
        """Тест форматирования размера файла в гигабайтах"""
        # Файл размером 1GB
        result = filesize(self.large_file)
        self.assertEqual(result, "1.0 GB")
        
        # Файл размером 2GB
        result = filesize(self.very_large_file)
        self.assertEqual(result, "2.0 GB")

    def test_filesize_edge_cases(self):
        """Тест граничных случаев форматирования размера"""
        # Файл размером ровно 1024 байта
        exact_kb_file = SimpleUploadedFile(
            "exact_kb.txt",
            b"x" * 1024,
            content_type="text/plain"
        )
        result = filesize(exact_kb_file)
        self.assertEqual(result, "1.0 KB")
        
        # Файл размером 1023 байта
        almost_kb_file = SimpleUploadedFile(
            "almost_kb.txt",
            b"x" * 1023,
            content_type="text/plain"
        )
        result = filesize(almost_kb_file)
        self.assertEqual(result, "1023 B")

    def test_filesize_none_input(self):
        """Тест обработки None входных данных"""
        result = filesize(None)
        self.assertEqual(result, "0 B")

    def test_filesize_empty_string(self):
        """Тест обработки пустой строки"""
        result = filesize("")
        self.assertEqual(result, "0 B")

    def test_filesize_invalid_input(self):
        """Тест обработки невалидных входных данных"""
        # Передаем число вместо файла
        result = filesize(123)
        self.assertEqual(result, "Неизвестно")
        
        # Передаем список
        result = filesize([1, 2, 3])
        self.assertEqual(result, "Неизвестно")

    def test_filename_extraction(self):
        """Тест извлечения имени файла"""
        # Обычное имя файла
        result = filename(self.small_file)
        self.assertEqual(result, "small.txt")
        
        # Имя файла с путем
        file_with_path = SimpleUploadedFile(
            "path/to/file.txt",
            b"content",
            content_type="text/plain"
        )
        result = filename(file_with_path)
        self.assertEqual(result, "file.txt")
        
        # Имя файла с расширением
        excel_file = SimpleUploadedFile(
            "order_123.xlsx",
            b"content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        result = filename(excel_file)
        self.assertEqual(result, "order_123.xlsx")

    def test_filename_none_input(self):
        """Тест обработки None входных данных для filename"""
        result = filename(None)
        self.assertEqual(result, "")

    def test_filename_empty_string(self):
        """Тест обработки пустой строки для filename"""
        result = filename("")
        self.assertEqual(result, "")

    def test_filename_invalid_input(self):
        """Тест обработки невалидных входных данных для filename"""
        # Передаем число
        result = filename(123)
        self.assertEqual(result, "123")
        
        # Передаем список
        result = filename([1, 2, 3])
        self.assertEqual(result, "[1, 2, 3]")

    def test_filesize_precision(self):
        """Тест точности форматирования размера"""
        # Файл размером 1.5MB
        one_and_half_mb = SimpleUploadedFile(
            "1.5mb.txt",
            b"x" * int(1.5 * 1024 * 1024),
            content_type="text/plain"
        )
        result = filesize(one_and_half_mb)
        self.assertEqual(result, "1.5 MB")
        
        # Файл размером 2.7GB
        two_point_seven_gb = SimpleUploadedFile(
            "2.7gb.txt",
            b"x" * int(2.7 * 1024 * 1024 * 1024),
            content_type="text/plain"
        )
        result = filesize(two_point_seven_gb)
        self.assertEqual(result, "2.7 GB")

    def test_filesize_terabytes(self):
        """Тест форматирования размера файла в терабайтах"""
        # Файл размером 1TB
        one_tb_file = SimpleUploadedFile(
            "1tb.txt",
            b"x" * (1024 * 1024 * 1024 * 1024),  # 1TB
            content_type="text/plain"
        )
        result = filesize(one_tb_file)
        self.assertEqual(result, "1.0 TB")

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

    def test_filename_with_special_characters(self):
        """Тест обработки имен файлов со специальными символами"""
        special_file = SimpleUploadedFile(
            "file-with_special.chars.txt",
            b"content",
            content_type="text/plain"
        )
        result = filename(special_file)
        self.assertEqual(result, "file-with_special.chars.txt")


@pytest.mark.django_db
class TemplateFiltersPytestTestCase:
    """Тесты с использованием pytest для template filters"""
    
    def test_filesize_formatting_pytest(self):
        """Тест форматирования размера файла с pytest"""
        # Создаем файл размером 1KB
        small_file = SimpleUploadedFile(
            "small.txt",
            b"x" * 1024,
            content_type="text/plain"
        )
        
        result = filesize(small_file)
        assert result == "1.0 KB"
        
        # Создаем файл размером 1MB
        medium_file = SimpleUploadedFile(
            "medium.txt",
            b"x" * (1024 * 1024),
            content_type="text/plain"
        )
        
        result = filesize(medium_file)
        assert result == "1.0 MB"

    def test_filename_extraction_pytest(self):
        """Тест извлечения имени файла с pytest"""
        # Обычное имя файла
        file = SimpleUploadedFile(
            "test.xlsx",
            b"content",
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        result = filename(file)
        assert result == "test.xlsx"
        
        # Имя файла с путем
        file_with_path = SimpleUploadedFile(
            "path/to/file.pdf",
            b"content",
            content_type="application/pdf"
        )
        
        result = filename(file_with_path)
        assert result == "file.pdf"

    def test_filesize_edge_cases_pytest(self):
        """Тест граничных случаев с pytest"""
        # Файл размером 0 байт
        empty_file = SimpleUploadedFile("empty.txt", b"", content_type="text/plain")
        result = filesize(empty_file)
        assert result == "0 B"
        
        # None входные данные
        result = filesize(None)
        assert result == "0 B"
        
        # Пустая строка
        result = filesize("")
        assert result == "0 B"

    def test_filename_edge_cases_pytest(self):
        """Тест граничных случаев для filename с pytest"""
        # None входные данные
        result = filename(None)
        assert result == ""
        
        # Пустая строка
        result = filename("")
        assert result == ""
        
        # Невалидные входные данные
        result = filename(123)
        assert result == "123"

    def test_filesize_precision_pytest(self):
        """Тест точности форматирования с pytest"""
        # Файл размером 1.5MB
        one_and_half_mb = SimpleUploadedFile(
            "1.5mb.txt",
            b"x" * int(1.5 * 1024 * 1024),
            content_type="text/plain"
        )
        result = filesize(one_and_half_mb)
        assert result == "1.5 MB"
        
        # Файл размером 2.7GB
        two_point_seven_gb = SimpleUploadedFile(
            "2.7gb.txt",
            b"x" * int(2.7 * 1024 * 1024 * 1024),
            content_type="text/plain"
        )
        result = filesize(two_point_seven_gb)
        assert result == "2.7 GB"

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
        
        # Гигабайты
        gb_file = SimpleUploadedFile("gb.txt", b"x" * (1024 * 1024 * 1024), content_type="text/plain")
        result = filesize(gb_file)
        assert result == "1.0 GB"
        
        # Терабайты
        tb_file = SimpleUploadedFile("tb.txt", b"x" * (1024 * 1024 * 1024 * 1024), content_type="text/plain")
        result = filesize(tb_file)
        assert result == "1.0 TB"
