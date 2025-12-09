from django.conf import settings
from .models import Notification


def notification_count(request):
    """Контекстный процессор для подсчета непрочитанных уведомлений"""
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications_count': unread_count}
    return {'unread_notifications_count': 0}


def app_version(request):
    """Контекстный процессор для версии приложения"""
    return {'app_version': getattr(settings, 'VERSION', '1.0.0')}
