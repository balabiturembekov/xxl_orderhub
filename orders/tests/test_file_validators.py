import pytest
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from orders.validators import (
    validate_file_type, 
    validate_file_size, 
    validate_excel_file, 
    validate_pdf_file,
    validate_safe_filename
)


class FileValidatorsTestCase(TestCase):
    """Тесты для валидаторов файлов"""
    
    def setUp(self):
        # Создаем валидный Excel файл
        self.valid_excel_content = self._create_valid_excel()
        self.valid_excel_file = SimpleUploadedFile(
            "test.xlsx",
            self.valid_excel_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Создаем валидный PDF файл
        self.valid_pdf_content = self._create_valid_pdf()
        self.valid_pdf_file = SimpleUploadedFile(
            "test.pdf",
            self.valid_pdf_content,
            content_type="application/pdf"
        )
        
        # Создаем невалидные файлы
        self.invalid_file = SimpleUploadedFile(
            "test.txt",
            b"This is not a valid file",
            content_type="text/plain"
        )
        
        # Создаем большой файл (больше 500MB)
        self.large_file = SimpleUploadedFile(
            "large.xlsx",
            b"x" * (600 * 1024 * 1024),  # 600MB
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    def _create_valid_excel(self):
        """Создает валидный Excel файл"""
        import zipfile
        import io
        
        xlsx_buffer = io.BytesIO()
        with zipfile.ZipFile(xlsx_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            zip_file.writestr('[Content_Types].xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
    <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
    <Default Extension="xml" ContentType="application/xml"/>
    <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
</Types>''')
            zip_file.writestr('_rels/.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')
            zip_file.writestr('xl/workbook.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <sheets>
        <sheet name="Sheet1" sheetId="1" r:id="rId1"/>
    </sheets>
</workbook>''')
            zip_file.writestr('xl/_rels/workbook.xml.rels', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
    <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>''')
            zip_file.writestr('xl/worksheets/sheet1.xml', '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
    <sheetData>
        <row r="1">
            <c r="A1" t="str">
                <v>Test</v>
            </c>
        </row>
    </sheetData>
</worksheet>''')
        
        return xlsx_buffer.getvalue()

    def _create_valid_pdf(self):
        """Создает валидный PDF файл"""
        return b'''%PDF-1.4
1 0 obj
<<
/Type /Catalog
/Pages 2 0 R
>>
endobj

2 0 obj
<<
/Type /Pages
/Kids [3 0 R]
/Count 1
>>
endobj

3 0 obj
<<
/Type /Page
/Parent 2 0 R
/MediaBox [0 0 612 792]
/Contents 4 0 R
>>
endobj

4 0 obj
<<
/Length 44
>>
stream
BT
/F1 12 Tf
72 720 Td
(Test PDF) Tj
ET
endstream
endobj

xref
0 5
0000000000 65535 f 
0000000009 00000 n 
0000000058 00000 n 
0000000115 00000 n 
0000000204 00000 n 
trailer
<<
/Size 5
/Root 1 0 R
>>
startxref
297
%%EOF'''

    def test_validate_file_size_valid(self):
        """Тест валидации размера файла - валидный размер"""
        # Файл размером 1MB должен пройти валидацию
        small_file = SimpleUploadedFile(
            "small.xlsx",
            b"x" * (1 * 1024 * 1024),  # 1MB
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Не должно вызывать исключение
        validate_file_size(small_file)

    def test_validate_file_size_invalid(self):
        """Тест валидации размера файла - невалидный размер"""
        with self.assertRaises(ValidationError) as context:
            validate_file_size(self.large_file)
        
        self.assertIn('Файл слишком большой', str(context.exception))
        self.assertIn('500MB', str(context.exception))

    def test_validate_file_type_excel_valid(self):
        """Тест валидации типа файла - валидный Excel"""
        # Не должно вызывать исключение
        validate_file_type(self.valid_excel_file)

    def test_validate_file_type_pdf_valid(self):
        """Тест валидации типа файла - валидный PDF"""
        # Не должно вызывать исключение
        validate_file_type(self.valid_pdf_file)

    def test_validate_file_type_invalid(self):
        """Тест валидации типа файла - невалидный файл"""
        with self.assertRaises(ValidationError) as context:
            validate_file_type(self.invalid_file)
        
        self.assertIn('Недопустимый тип файла', str(context.exception))

    def test_validate_excel_file_valid(self):
        """Тест валидации Excel файла - валидный файл"""
        # Не должно вызывать исключение
        validate_excel_file(self.valid_excel_file)

    def test_validate_excel_file_invalid_type(self):
        """Тест валидации Excel файла - невалидный тип"""
        with self.assertRaises(ValidationError) as context:
            validate_excel_file(self.invalid_file)
        
        self.assertIn('Файл должен иметь расширение .xlsx или .xls', str(context.exception))

    def test_validate_excel_file_invalid_extension(self):
        """Тест валидации Excel файла - невалидное расширение"""
        invalid_excel = SimpleUploadedFile(
            "test.doc",
            self.valid_excel_content,
            content_type="application/msword"
        )
        
        with self.assertRaises(ValidationError) as context:
            validate_excel_file(invalid_excel)
        
        self.assertIn('Файл должен иметь расширение', str(context.exception))

    def test_validate_pdf_file_valid(self):
        """Тест валидации PDF файла - валидный файл"""
        # Не должно вызывать исключение
        validate_pdf_file(self.valid_pdf_file)

    def test_validate_pdf_file_invalid_type(self):
        """Тест валидации PDF файла - невалидный тип"""
        with self.assertRaises(ValidationError) as context:
            validate_pdf_file(self.invalid_file)
        
        self.assertIn('Файл должен иметь расширение .pdf', str(context.exception))

    def test_validate_pdf_file_invalid_extension(self):
        """Тест валидации PDF файла - невалидное расширение"""
        invalid_pdf = SimpleUploadedFile(
            "test.doc",
            self.valid_pdf_content,
            content_type="application/msword"
        )
        
        with self.assertRaises(ValidationError) as context:
            validate_pdf_file(invalid_pdf)
        
        self.assertIn('Файл должен иметь расширение .pdf', str(context.exception))

    def test_validate_pdf_file_invalid_content(self):
        """Тест валидации PDF файла - невалидное содержимое"""
        fake_pdf = SimpleUploadedFile(
            "fake.pdf",
            b"This is not a PDF file",
            content_type="application/pdf"
        )
        
        with self.assertRaises(ValidationError) as context:
            validate_pdf_file(fake_pdf)
        
        self.assertIn('Файл не является корректным PDF файлом', str(context.exception))

    def test_validate_safe_filename_valid(self):
        """Тест валидации безопасного имени файла - валидные имена"""
        valid_names = [
            "test.xlsx",
            "order_123.xlsx",
            "файл-заказа.xlsx",
            "file with spaces.xlsx"
        ]
        
        for name in valid_names:
            # Не должно вызывать исключение
            validate_safe_filename(name)

    def test_validate_safe_filename_invalid(self):
        """Тест валидации безопасного имени файла - невалидные имена"""
        invalid_names = [
            "../../../etc/passwd",  # содержит ..
            "file|name.xlsx",       # содержит |
            "file:name.xlsx",       # содержит :
            "file*name.xlsx",       # содержит *
            "file?name.xlsx",       # содержит ?
            "file<name.xlsx",       # содержит <
            "file>name.xlsx"       # содержит >
        ]
        
        for name in invalid_names:
            with self.assertRaises(ValidationError) as context:
                validate_safe_filename(name)
            
            self.assertIn('Имя файла содержит недопустимые символы', str(context.exception))

    def test_file_size_edge_cases(self):
        """Тест граничных случаев размера файла"""
        # Файл размером ровно 500MB
        exact_size_file = SimpleUploadedFile(
            "exact.xlsx",
            b"x" * (500 * 1024 * 1024),  # Ровно 500MB
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Не должно вызывать исключение
        validate_file_size(exact_size_file)
        
        # Файл размером 500MB + 1 байт
        too_large_file = SimpleUploadedFile(
            "too_large.xlsx",
            b"x" * (500 * 1024 * 1024) + b"x",  # 500MB + 1 байт
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        with self.assertRaises(ValidationError):
            validate_file_size(too_large_file)

    def test_excel_file_signatures(self):
        """Тест различных сигнатур Excel файлов"""
        # Тест .xlsx файла (ZIP сигнатура)
        xlsx_content = b'PK\x03\x04' + b'x' * 100
        xlsx_file = SimpleUploadedFile(
            "test.xlsx",
            xlsx_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Не должно вызывать исключение
        validate_excel_file(xlsx_file)
        
        # Тест .xls файла (OLE сигнатура)
        xls_content = b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + b'x' * 100
        xls_file = SimpleUploadedFile(
            "test.xls",
            xls_content,
            content_type="application/vnd.ms-excel"
        )
        
        # Не должно вызывать исключение
        validate_excel_file(xls_file)

    def test_pdf_file_signature(self):
        """Тест сигнатуры PDF файла"""
        # PDF файл должен начинаться с %PDF
        pdf_content = b'%PDF-1.4\n' + b'x' * 100
        pdf_file = SimpleUploadedFile(
            "test.pdf",
            pdf_content,
            content_type="application/pdf"
        )
        
        # Не должно вызывать исключение
        validate_pdf_file(pdf_file)


@pytest.mark.django_db
class FileValidatorsPytestTestCase:
    """Тесты с использованием pytest для валидаторов файлов"""
    
    def test_file_size_validation_pytest(self):
        """Тест валидации размера файла с pytest"""
        from django.core.exceptions import ValidationError
        
        # Создаем файл размером 1MB
        small_file = SimpleUploadedFile(
            "small.xlsx",
            b"x" * (1 * 1024 * 1024),  # 1MB
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Не должно вызывать исключение
        validate_file_size(small_file)
        
        # Создаем файл размером 600MB
        large_file = SimpleUploadedFile(
            "large.xlsx",
            b"x" * (600 * 1024 * 1024),  # 600MB
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Должно вызывать исключение
        with pytest.raises(ValidationError) as exc_info:
            validate_file_size(large_file)
        
        assert 'Файл слишком большой' in str(exc_info.value)
        assert '500MB' in str(exc_info.value)

    def test_file_type_validation_pytest(self):
        """Тест валидации типа файла с pytest"""
        from django.core.exceptions import ValidationError
        
        # Создаем валидный Excel файл
        excel_content = b'PK\x03\x04' + b'x' * 100
        excel_file = SimpleUploadedFile(
            "test.xlsx",
            excel_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # Не должно вызывать исключение
        validate_file_type(excel_file)
        
        # Создаем невалидный файл
        invalid_file = SimpleUploadedFile(
            "test.txt",
            b"This is not a valid file",
            content_type="text/plain"
        )
        
        # Должно вызывать исключение
        with pytest.raises(ValidationError) as exc_info:
            validate_file_type(invalid_file)
        
        assert 'Недопустимый тип файла' in str(exc_info.value)

    def test_safe_filename_validation_pytest(self):
        """Тест валидации безопасного имени файла с pytest"""
        from django.core.exceptions import ValidationError
        
        # Валидные имена
        valid_names = ["test.xlsx", "order_123.xlsx", "файл-заказа.xlsx"]
        for name in valid_names:
            validate_safe_filename(name)  # Не должно вызывать исключение
        
        # Невалидные имена
        invalid_names = ["../../../etc/passwd", "file\x00name.xlsx"]
        for name in invalid_names:
            with pytest.raises(ValidationError) as exc_info:
                validate_safe_filename(name)
            
            assert 'Недопустимое имя файла' in str(exc_info.value)
