import os
import magic
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .constants import FileConstants


def validate_file_type(file):
    """Валидация типа файла по содержимому"""
    # Читаем первые 1024 байта для определения MIME типа
    file.seek(0)
    file_content = file.read(1024)
    file.seek(0)  # Возвращаем указатель в начало
    
    # Определяем MIME тип с обработкой ошибок
    try:
        mime_type = magic.from_buffer(file_content, mime=True)
    except Exception:
        # Если magic не работает, используем только проверку сигнатур
        mime_type = None
    
    # Проверяем расширение файла
    file_extension = file.name.lower().split('.')[-1] if '.' in file.name else ''
    is_excel_extension = file_extension in ['xlsx', 'xls']
    is_pdf_extension = file_extension == 'pdf'
    
    # Проверка для Excel файлов
    if is_excel_extension:
        # Проверяем сигнатуры Excel файлов (приоритет сигнатурам, они быстрее)
        if (file_content.startswith(b'PK\x03\x04') or  # ZIP/Office signature (.xlsx)
            file_content.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')):  # OLE signature (.xls)
            return
        # Если сигнатуры не подошли, проверяем MIME тип
        if mime_type and mime_type in ['application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                                       'application/vnd.ms-excel',
                                       'application/octet-stream',
                                       'application/zip']:
            return
    
    # Проверка для PDF файлов
    if is_pdf_extension:
        # Проверяем сигнатуру PDF (приоритет сигнатуре)
        if file_content.startswith(b'%PDF'):
            return
        # Если сигнатура не подошла, проверяем MIME тип
        if mime_type == 'application/pdf':
            return
    
    # Если MIME тип в списке разрешенных (для обратной совместимости)
    if mime_type:
        allowed_mime_types = {
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # .xlsx
            'application/vnd.ms-excel',  # .xls
            'application/pdf',  # .pdf
        }
        
        if mime_type in allowed_mime_types:
            return
    
    # Если ничего не подошло - ошибка
    raise ValidationError(
        _('Недопустимый тип файла. Разрешены только Excel (.xlsx, .xls) и PDF файлы.'),
        code='invalid_file_type'
    )


def validate_file_size(file):
    """Валидация размера файла"""
    max_size = FileConstants.MAX_EXCEL_SIZE  # 2GB
    
    # Проверка на наличие размера файла
    if not hasattr(file, 'size') or file.size is None:
        raise ValidationError(
            _('Не удалось определить размер файла.'),
            code='file_size_error'
        )
    
    if file.size > max_size:
        max_size_mb = FileConstants.MAX_EXCEL_SIZE_MB
        raise ValidationError(
            _('Файл слишком большой. Максимальный размер: {}MB.').format(max_size_mb),
            code='file_too_large'
        )


def validate_excel_file(file):
    """Валидация Excel файла"""
    # Проверка на наличие файла
    if not file:
        raise ValidationError(
            _('Файл не загружен.'),
            code='file_missing'
        )
    
    # Проверка на наличие имени файла
    if not hasattr(file, 'name') or not file.name:
        raise ValidationError(
            _('Не удалось определить имя файла.'),
            code='file_name_error'
        )
    
    validate_file_size(file)
    
    # Проверка расширения файла
    if not file.name.lower().endswith(('.xlsx', '.xls')):
        raise ValidationError(
            _('Файл должен иметь расширение .xlsx или .xls'),
            code='invalid_extension'
        )
    
    # Проверка типа файла по содержимому
    try:
        file.seek(0)
        file_content = file.read(1024)
        file.seek(0)  # Возвращаем указатель в начало
        
        # Проверяем сигнатуры Excel файлов
        if not (file_content.startswith(b'PK\x03\x04') or  # ZIP/Office signature (.xlsx)
                file_content.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1')):  # OLE signature (.xls)
            raise ValidationError(
                _('Файл не является корректным Excel файлом'),
                code='invalid_excel_file'
            )
    except Exception as e:
        # Если не удалось прочитать файл, это может быть проблема с большим файлом
        # Но мы уже проверили размер, так что это скорее всего ошибка чтения
        raise ValidationError(
            _('Ошибка при чтении файла: {}').format(str(e)),
            code='file_read_error'
        )


def validate_pdf_file(file):
    """Валидация PDF файла"""
    # Проверка на наличие файла
    if not file:
        raise ValidationError(
            _('Файл не загружен.'),
            code='file_missing'
        )
    
    # Проверка на наличие имени файла
    if not hasattr(file, 'name') or not file.name:
        raise ValidationError(
            _('Не удалось определить имя файла.'),
            code='file_name_error'
        )
    
    validate_file_size(file)
    
    # Проверка расширения файла
    if not file.name.lower().endswith('.pdf'):
        raise ValidationError(
            _('Файл должен иметь расширение .pdf'),
            code='invalid_extension'
        )
    
    # Проверка типа файла по содержимому
    try:
        file.seek(0)
        file_content = file.read(1024)
        file.seek(0)  # Возвращаем указатель в начало
        
        # Проверяем сигнатуру PDF файла
        if not file_content.startswith(b'%PDF'):
            raise ValidationError(
                _('Файл не является корректным PDF файлом'),
                code='invalid_pdf_file'
            )
    except Exception as e:
        # Если не удалось прочитать файл
        raise ValidationError(
            _('Ошибка при чтении файла: {}').format(str(e)),
            code='file_read_error'
        )


def validate_safe_filename(filename):
    """Валидация имени файла на безопасность"""
    # Запрещенные символы
    dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
    
    for char in dangerous_chars:
        if char in filename:
            raise ValidationError(
                _('Имя файла содержит недопустимые символы: {}').format(char),
                code='dangerous_filename'
            )
    
    # Проверка длины
    if len(filename) > 255:
        raise ValidationError(
            _('Имя файла слишком длинное. Максимум 255 символов.'),
            code='filename_too_long'
        )
    
    # Проверка на пустое имя
    if not filename.strip():
        raise ValidationError(
            _('Имя файла не может быть пустым'),
            code='empty_filename'
        )
