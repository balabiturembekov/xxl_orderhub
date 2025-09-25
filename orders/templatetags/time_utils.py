"""
Template filters for time and date formatting.

This module provides custom template filters for proper timezone-aware
date and time formatting in templates.
"""

from django import template
from django.utils import timezone
from django.utils.dateformat import format
import pytz

register = template.Library()


@register.filter
def localtime(value):
    """
    Convert UTC datetime to local timezone.
    
    Usage: {{ order.uploaded_at|localtime }}
    """
    if not value:
        return value
    
    if timezone.is_aware(value):
        return timezone.localtime(value)
    return value


@register.filter
def timezone_format(value, format_string="d.m.Y H:i"):
    """
    Format datetime with timezone information.
    
    Usage: {{ order.uploaded_at|timezone_format:"d.m.Y H:i" }}
    """
    if not value:
        return value
    
    if timezone.is_aware(value):
        local_time = timezone.localtime(value)
        return local_time.strftime(format_string.replace('d', '%d').replace('m', '%m').replace('Y', '%Y').replace('H', '%H').replace('i', '%M'))
    return value


@register.filter
def timezone_name(value):
    """
    Get timezone name for datetime.
    
    Usage: {{ order.uploaded_at|timezone_name }}
    """
    if not value:
        return ""
    
    if timezone.is_aware(value):
        local_time = timezone.localtime(value)
        return local_time.tzname()
    return "UTC"


@register.filter
def time_ago(value):
    """
    Show relative time (e.g., "2 hours ago").
    
    Usage: {{ order.uploaded_at|time_ago }}
    """
    if not value:
        return value
    
    if timezone.is_aware(value):
        local_time = timezone.localtime(value)
    else:
        local_time = value
    
    now = timezone.now()
    if timezone.is_aware(now):
        now = timezone.localtime(now)
    
    diff = now - local_time
    
    if diff.days > 0:
        return f"{diff.days} дн. назад"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} ч. назад"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} мин. назад"
    else:
        return "только что"


@register.filter
def business_hours(value):
    """
    Format time for business hours display.
    
    Usage: {{ order.uploaded_at|business_hours }}
    """
    if not value:
        return value
    
    if timezone.is_aware(value):
        local_time = timezone.localtime(value)
    else:
        local_time = value
    
    # Check if it's business hours (9:00 - 18:00)
    hour = local_time.hour
    if 9 <= hour < 18:
        status = "рабочее время"
        color = "text-success"
    elif 18 <= hour < 22:
        status = "вечернее время"
        color = "text-warning"
    else:
        status = "вне рабочего времени"
        color = "text-muted"
    
    return f'<span class="{color}">{status}</span>'


@register.filter
def european_date(value):
    """
    Format date in European format (DD.MM.YYYY).
    
    Usage: {{ order.uploaded_at|european_date }}
    """
    if not value:
        return value
    
    if timezone.is_aware(value):
        local_time = timezone.localtime(value)
    else:
        local_time = value
    
    return local_time.strftime("%d.%m.%Y")


@register.filter
def european_datetime(value):
    """
    Format datetime in European format (DD.MM.YYYY HH:MM).
    
    Usage: {{ order.uploaded_at|european_datetime }}
    """
    if not value:
        return value
    
    if timezone.is_aware(value):
        local_time = timezone.localtime(value)
    else:
        local_time = value
    
    return local_time.strftime("%d.%m.%Y %H:%M")


@register.filter
def european_datetime_full(value):
    """
    Format datetime in European format with timezone (DD.MM.YYYY HH:MM TZ).
    
    Usage: {{ order.uploaded_at|european_datetime_full }}
    """
    if not value:
        return value
    
    if timezone.is_aware(value):
        local_time = timezone.localtime(value)
        tz_name = local_time.tzname()
        return f"{local_time.strftime('%d.%m.%Y %H:%M')} {tz_name}"
    else:
        return value.strftime("%d.%m.%Y %H:%M UTC")
