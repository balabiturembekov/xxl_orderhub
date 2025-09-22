from .models import Notification


def notification_count(request):
    """Контекстный процессор для подсчета непрочитанных уведомлений"""
    if request.user.is_authenticated:
        unread_count = Notification.objects.filter(user=request.user, is_read=False).count()
        return {'unread_notifications_count': unread_count}
    return {'unread_notifications_count': 0}
