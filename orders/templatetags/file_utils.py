from django import template
import os

register = template.Library()

@register.filter
def abs_value(value):
    """
    Возвращает абсолютное значение числа.
    
    Args:
        value: Число (int, float, Decimal)
        
    Returns:
        Абсолютное значение числа
    """
    try:
        if value is None:
            return None
        return abs(value)
    except (TypeError, ValueError):
        return value

@register.filter
def filesize(value):
    """
    Форматирует размер файла в читаемый вид.
    
    Args:
        value: FileField или путь к файлу
        
    Returns:
        str: Отформатированный размер файла (например, "1.5 MB")
    """
    if not value:
        return "0 B"
    
    try:
        # Если это SimpleUploadedFile или объект с атрибутом size
        if hasattr(value, 'size'):
            size_bytes = value.size
        # Если это FileField, получаем путь к файлу
        elif hasattr(value, 'path'):
            file_path = value.path
            if os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
            else:
                return "Файл не найден"
        elif hasattr(value, 'url'):
            # Если файл существует, получаем его размер
            if os.path.exists(value.path):
                file_path = value.path
                size_bytes = os.path.getsize(file_path)
            else:
                return "Файл не найден"
        else:
            # Если это строка с путем
            file_path = str(value)
            if os.path.exists(file_path):
                size_bytes = os.path.getsize(file_path)
            else:
                return "Файл не найден"
        
        # Форматируем размер
        return format_file_size(size_bytes)
        
    except (OSError, ValueError, AttributeError):
        return "Неизвестно"

def format_file_size(size_bytes):
    """
    Форматирует размер файла в байтах в читаемый вид.
    
    Args:
        size_bytes: Размер в байтах
        
    Returns:
        str: Отформатированный размер
    """
    if size_bytes == 0:
        return "0 B"
    
    # Определяем единицы измерения
    units = ['B', 'KB', 'MB', 'GB', 'TB']
    unit_index = 0
    size = float(size_bytes)
    
    # Конвертируем в подходящую единицу
    while size >= 1024 and unit_index < len(units) - 1:
        size /= 1024
        unit_index += 1
    
    # Форматируем число
    if unit_index == 0:
        return f"{int(size)} {units[unit_index]}"
    else:
        return f"{size:.1f} {units[unit_index]}"

@register.filter
def filename(value):
    """
    Извлекает имя файла из пути.
    
    Args:
        value: FileField или путь к файлу
        
    Returns:
        str: Имя файла
    """
    if not value:
        return ""
    
    try:
        if hasattr(value, 'name'):
            return os.path.basename(value.name)
        else:
            return os.path.basename(str(value))
    except (AttributeError, ValueError):
        return str(value)
