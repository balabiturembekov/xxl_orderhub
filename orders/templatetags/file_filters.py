from django import template
import os

register = template.Library()

@register.filter
def basename(value):
    """Возвращает только имя файла без пути"""
    if not value:
        return ""
    return os.path.basename(str(value))

@register.filter
def filesize(value):
    """Возвращает размер файла в читаемом формате"""
    if not value:
        return "0 B"
    
    size = int(value)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} TB"
