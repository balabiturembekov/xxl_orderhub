from celery import shared_task
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.db import models
from datetime import timedelta
from .models import Order, Notification, NotificationSettings, NotificationTemplate, Invoice
from .constants import TimeConstants


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_email(self, notification_id):
    """Отправка email уведомления с retry механизмом"""
    try:
        notification = Notification.objects.get(id=notification_id)
        user = notification.user
        
        # Проверяем настройки пользователя
        try:
            settings_obj = NotificationSettings.objects.get(user=user)
            if not settings_obj.email_notifications:
                return f"Email уведомления отключены для пользователя {user.username}"
        except NotificationSettings.DoesNotExist:
            # Если настройки не найдены, создаем их с настройками по умолчанию
            settings_obj = NotificationSettings.objects.create(user=user)
        
        # Получаем шаблон уведомления
        try:
            template = NotificationTemplate.objects.get(
                template_type=notification.notification_type,
                is_active=True
            )
        except NotificationTemplate.DoesNotExist:
            # Если шаблон не найден, используем базовый шаблон
            subject = notification.title
            message = notification.message
        else:
            subject = template.subject
            # Рендерим HTML шаблон
            html_message = render_to_string('emails/notification.html', {
                'notification': notification,
                'order': notification.order,
                'user': user,
                'template': template,
                'base_url': settings.BASE_URL
            })
            # Рендерим текстовый шаблон
            message = render_to_string('emails/notification.txt', {
                'notification': notification,
                'order': notification.order,
                'user': user,
                'template': template,
                'base_url': settings.BASE_URL
            })
        
        # Отправляем email
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            html_message=html_message if 'html_message' in locals() else None,
            fail_silently=False,
        )
        
        # Отмечаем уведомление как отправленное
        notification.mark_as_sent()
        
        return f"Email отправлен пользователю {user.username} для заказа {notification.order.title}"
        
    except Exception as e:
        # Логируем ошибку
        import logging
        logger = logging.getLogger('orders')
        logger.error(f"Ошибка при отправке email для уведомления {notification_id}: {str(e)}")
        
        # Retry при временных ошибках
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return f"Ошибка при отправке email после {self.max_retries} попыток: {str(e)}"


@shared_task
def check_overdue_orders():
    """Проверка просроченных заказов и отправка напоминаний"""
    now = timezone.now()
    notifications_sent = 0
    
    # Получаем все заказы, которые нуждаются в напоминаниях
    # Используем настройки пользователя для определения периода
    overdue_orders = Order.objects.filter(
        models.Q(
            status='uploaded',
            uploaded_at__lte=now - timedelta(days=TimeConstants.MIN_REMINDER_DAYS)  # Минимум 1 день
        ) | models.Q(
            status='sent',
            sent_at__lte=now - timedelta(days=TimeConstants.MIN_REMINDER_DAYS)  # Минимум 1 день
        )
    ).select_related('employee', 'factory')
    
    for order in overdue_orders:
        # Проверяем настройки пользователя
        try:
            settings_obj = NotificationSettings.objects.get(user=order.employee)
            if not settings_obj.email_notifications:
                continue
        except NotificationSettings.DoesNotExist:
            # Создаем настройки по умолчанию
            settings_obj = NotificationSettings.objects.create(user=order.employee)
        
        # Определяем тип уведомления
        if order.status == 'uploaded' and settings_obj.notify_uploaded_reminder:
            notification_type = 'uploaded_reminder'
            title = f"Напоминание: заказ '{order.title}' не отправлен уже {order.days_since_upload} дней"
            message = f"Заказ '{order.title}' для фабрики '{order.factory.name}' был загружен {order.days_since_upload} дней назад, но еще не отправлен. Рекомендуется отправить заказ на фабрику."
        elif order.status == 'sent' and settings_obj.notify_sent_reminder:
            notification_type = 'sent_reminder'
            title = f"Напоминание: заказ '{order.title}' отправлен, но инвойс не получен уже {order.days_since_sent} дней"
            message = f"Заказ '{order.title}' для фабрики '{order.factory.name}' был отправлен {order.days_since_sent} дней назад, но инвойс еще не получен. Рекомендуется связаться с фабрикой."
        else:
            continue
        
        # Проверяем, не отправляли ли мы уже напоминание недавно
        last_reminder = Notification.objects.filter(
            user=order.employee,
            order=order,
            notification_type=notification_type,
            created_at__gte=now - timedelta(days=settings_obj.reminder_frequency)
        ).first()
        
        if last_reminder:
            continue
        
        # Создаем уведомление
        notification = Notification.objects.create(
            user=order.employee,
            order=order,
            notification_type=notification_type,
            title=title,
            message=message
        )
        
        # Отправляем email асинхронно
        send_notification_email.delay(notification.id)
        notifications_sent += 1
    
    return f"Отправлено {notifications_sent} напоминаний о просроченных заказах"


@shared_task
def send_order_notification(order_id, notification_type):
    """Отправка уведомления о изменении статуса заказа"""
    try:
        order = Order.objects.get(id=order_id)
        user = order.employee
        
        # Проверяем настройки пользователя
        try:
            settings_obj = NotificationSettings.objects.get(user=user)
            if not settings_obj.email_notifications:
                return f"Email уведомления отключены для пользователя {user.username}"
        except NotificationSettings.DoesNotExist:
            settings_obj = NotificationSettings.objects.create(user=user)
        
        # Определяем заголовок и сообщение в зависимости от типа
        if notification_type == 'order_uploaded':
            title = f"Заказ '{order.title}' загружен"
            message = f"Заказ '{order.title}' для фабрики '{order.factory.name}' успешно загружен. Не забудьте отправить его на фабрику."
        elif notification_type == 'order_sent':
            if not settings_obj.notify_invoice_received:
                return "Уведомления о отправке заказов отключены"
            title = f"Заказ '{order.title}' отправлен на фабрику"
            message = f"Заказ '{order.title}' успешно отправлен на фабрику '{order.factory.name}'. Ожидайте инвойс от фабрики."
        elif notification_type == 'invoice_received':
            if not settings_obj.notify_invoice_received:
                return "Уведомления о получении инвойсов отключены"
            title = f"Инвойс получен для заказа '{order.title}'"
            message = f"Инвойс для заказа '{order.title}' от фабрики '{order.factory.name}' успешно получен и прикреплен к заказу."
        elif notification_type == 'order_completed':
            title = f"Заказ '{order.title}' завершен"
            message = f"Заказ '{order.title}' от фабрики '{order.factory.name}' успешно завершен."
        else:
            return f"Неизвестный тип уведомления: {notification_type}"
        
        # Создаем уведомление
        notification = Notification.objects.create(
            user=user,
            order=order,
            notification_type=notification_type,
            title=title,
            message=message
        )
        
        # Отправляем email асинхронно
        send_notification_email.delay(notification.id)
        
        return f"Уведомление отправлено пользователю {user.username} для заказа {order.title}"
        
    except Order.DoesNotExist:
        return f"Заказ с ID {order_id} не найден"
    except Exception as e:
        return f"Ошибка при отправке уведомления: {str(e)}"


@shared_task
def create_default_notification_templates():
    """Создание шаблонов уведомлений по умолчанию"""
    templates_data = [
        {
            'template_type': 'uploaded_reminder',
            'subject': 'Напоминание: заказ не отправлен',
            'html_template': '''
            <h2>Напоминание о неотправленном заказе</h2>
            <p>Здравствуйте, {{ user.first_name|default:user.username }}!</p>
            <p>Заказ <strong>{{ order.title }}</strong> для фабрики <strong>{{ order.factory.name }}</strong> был загружен {{ order.days_since_upload }} дней назад, но еще не отправлен.</p>
            <p>Рекомендуется отправить заказ на фабрику как можно скорее.</p>
            <p><a href="{{ order.get_absolute_url }}">Перейти к заказу</a></p>
            ''',
            'text_template': '''
            Напоминание о неотправленном заказе
            
            Здравствуйте, {{ user.first_name|default:user.username }}!
            
            Заказ "{{ order.title }}" для фабрики "{{ order.factory.name }}" был загружен {{ order.days_since_upload }} дней назад, но еще не отправлен.
            
            Рекомендуется отправить заказ на фабрику как можно скорее.
            '''
        },
        {
            'template_type': 'sent_reminder',
            'subject': 'Напоминание: ожидается инвойс',
            'html_template': '''
            <h2>Напоминание о заказе без инвойса</h2>
            <p>Здравствуйте, {{ user.first_name|default:user.username }}!</p>
            <p>Заказ <strong>{{ order.title }}</strong> для фабрики <strong>{{ order.factory.name }}</strong> был отправлен {{ order.days_since_sent }} дней назад, но инвойс еще не получен.</p>
            <p>Рекомендуется связаться с фабрикой для уточнения статуса заказа.</p>
            <p><a href="{{ order.get_absolute_url }}">Перейти к заказу</a></p>
            ''',
            'text_template': '''
            Напоминание о заказе без инвойса
            
            Здравствуйте, {{ user.first_name|default:user.username }}!
            
            Заказ "{{ order.title }}" для фабрики "{{ order.factory.name }}" был отправлен {{ order.days_since_sent }} дней назад, но инвойс еще не получен.
            
            Рекомендуется связаться с фабрикой для уточнения статуса заказа.
            '''
        },
        {
            'template_type': 'invoice_received',
            'subject': 'Инвойс получен',
            'html_template': '''
            <h2>Инвойс получен</h2>
            <p>Здравствуйте, {{ user.first_name|default:user.username }}!</p>
            <p>Инвойс для заказа <strong>{{ order.title }}</strong> от фабрики <strong>{{ order.factory.name }}</strong> успешно получен и прикреплен к заказу.</p>
            <p><a href="{{ order.get_absolute_url }}">Перейти к заказу</a></p>
            ''',
            'text_template': '''
            Инвойс получен
            
            Здравствуйте, {{ user.first_name|default:user.username }}!
            
            Инвойс для заказа "{{ order.title }}" от фабрики "{{ order.factory.name }}" успешно получен и прикреплен к заказу.
            '''
        }
    ]
    
    created_count = 0
    for template_data in templates_data:
        template, created = NotificationTemplate.objects.get_or_create(
            template_type=template_data['template_type'],
            defaults=template_data
        )
        if created:
            created_count += 1
    
    return f"Создано {created_count} шаблонов уведомлений"


@shared_task
def cleanup_old_notifications():
    """Очистка старых уведомлений (старше 30 дней)"""
    from datetime import timedelta
    
    cutoff_date = timezone.now() - timedelta(days=TimeConstants.METRICS_RETENTION_DAYS)
    old_notifications = Notification.objects.filter(
        created_at__lt=cutoff_date,
        is_read=True  # Удаляем только прочитанные
    )
    
    count = old_notifications.count()
    old_notifications.delete()
    
    return f"Удалено {count} старых уведомлений"


@shared_task
def generate_system_statistics():
    """Генерация ежедневной статистики системы"""
    from django.contrib.auth.models import User
    from django.db.models import Count, Q
    from datetime import timedelta
    
    now = timezone.now()
    yesterday = now - timedelta(days=TimeConstants.MIN_REMINDER_DAYS)
    
    # Статистика за вчера
    stats = {
        'date': yesterday.date(),
        'total_orders': Order.objects.filter(uploaded_at__date=yesterday.date()).count(),
        'new_orders': Order.objects.filter(uploaded_at__date=yesterday.date()).count(),
        'completed_orders': Order.objects.filter(
            completed_at__date=yesterday.date()
        ).count(),
        'overdue_orders': Order.objects.filter(
            Q(status='uploaded', uploaded_at__lte=now - timedelta(days=TimeConstants.LOG_RETENTION_DAYS)) |
            Q(status='sent', sent_at__lte=now - timedelta(days=TimeConstants.LOG_RETENTION_DAYS))
        ).count(),
        'active_users': User.objects.filter(
            last_login__date=yesterday.date()
        ).count(),
        'notifications_sent': Notification.objects.filter(
            created_at__date=yesterday.date()
        ).count(),
    }
    
    # Логируем статистику
    import logging
    logger = logging.getLogger('orders')
    logger.info(f"Daily statistics for {yesterday.date()}: {stats}")
    
    return f"Generated statistics for {yesterday.date()}: {stats['total_orders']} orders, {stats['completed_orders']} completed"


@shared_task
def check_overdue_payments():
    """Проверка просроченных платежей и отправка уведомлений"""
    now = timezone.now()
    notifications_sent = 0
    
    # Получаем все просроченные инвойсы
    overdue_invoices = Invoice.objects.filter(
        status='overdue',
        due_date__lt=now.date()
    ).select_related('order', 'order__employee', 'order__factory')
    
    for invoice in overdue_invoices:
        user = invoice.order.employee
        
        # Проверяем настройки пользователя
        try:
            settings_obj = NotificationSettings.objects.get(user=user)
            if not settings_obj.email_notifications:
                continue
        except NotificationSettings.DoesNotExist:
            settings_obj = NotificationSettings.objects.create(user=user)
        
        # Проверяем, не отправляли ли мы уже напоминание недавно
        last_reminder = Notification.objects.filter(
            user=user,
            order=invoice.order,
            notification_type='payment_overdue',
            created_at__gte=now - timedelta(days=settings_obj.reminder_frequency)
        ).first()
        
        if last_reminder:
            continue
        
        # Создаем уведомление
        days_overdue = (now.date() - invoice.due_date).days
        title = f"Просроченный платеж: инвойс {invoice.invoice_number}"
        message = f"Инвойс {invoice.invoice_number} для заказа '{invoice.order.title}' просрочен на {days_overdue} дней. Сумма к доплате: {invoice.remaining_amount}€"
        
        notification = Notification.objects.create(
            user=user,
            order=invoice.order,
            notification_type='payment_overdue',
            title=title,
            message=message
        )
        
        # Отправляем email асинхронно
        send_notification_email.delay(notification.id)
        notifications_sent += 1
    
    return f"Отправлено {notifications_sent} уведомлений о просроченных платежах"
