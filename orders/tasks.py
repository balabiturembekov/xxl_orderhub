from celery import shared_task
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.db import models
from datetime import timedelta
from email.header import Header
from .models import (
    Order,
    Notification,
    NotificationSettings,
    NotificationTemplate,
    Invoice,
)
from .constants import TimeConstants


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_notification_email(self, notification_id):
    """Отправка email уведомления с retry механизмом"""
    try:
        try:
            notification = Notification.objects.get(id=notification_id)
        except Notification.DoesNotExist:
            return f"Notification {notification_id} not found"

        user = notification.user

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-18: Проверяем наличие email адреса у пользователя
        if not user.email:
            return (
                f"User {user.username} has no email address. Cannot send notification."
            )

        # Проверяем настройки пользователя
        try:
            settings_obj = NotificationSettings.objects.get(user=user)
            if not settings_obj.email_notifications:
                return f"Email notifications disabled for user {user.username}"
        except NotificationSettings.DoesNotExist:
            # Если настройки не найдены, создаем их с настройками по умолчанию
            settings_obj = NotificationSettings.objects.create(user=user)

        # Получаем шаблон уведомления
        html_message = None
        text_message = None
        try:
            template = NotificationTemplate.objects.get(
                template_type=notification.notification_type, is_active=True
            )
            subject = template.subject
            # Рендерим HTML шаблон
            html_message = render_to_string(
                "emails/notification.html",
                {
                    "notification": notification,
                    "order": notification.order,
                    "user": user,
                    "template": template,
                    "base_url": settings.BASE_URL,
                },
            )
            # Рендерим текстовый шаблон
            text_message = render_to_string(
                "emails/notification.txt",
                {
                    "notification": notification,
                    "order": notification.order,
                    "user": user,
                    "template": template,
                    "base_url": settings.BASE_URL,
                },
            )
        except NotificationTemplate.DoesNotExist:
            # Если шаблон не найден, используем базовый шаблон
            subject = notification.title
            text_message = notification.message

        # Правильно кодируем subject для не-ASCII символов
        # Используем Header для правильной кодировки subject
        try:
            # Проверяем, есть ли не-ASCII символы в subject
            # Пытаемся закодировать в ASCII - если не получается, значит есть не-ASCII
            subject.encode("ascii")
            # Если успешно, значит только ASCII символы
            encoded_subject = subject
        except UnicodeEncodeError:
            # Есть не-ASCII символы, кодируем через Header
            encoded_subject = str(Header(subject, "utf-8"))
        except (AttributeError, UnicodeDecodeError):
            # В случае ошибки используем исходный subject
            encoded_subject = subject

        # Отправляем email с правильной кодировкой UTF-8
        # Используем альтернативный формат для HTML и текстовой версии
        if html_message:
            # Если есть HTML версия, используем её как основную и добавляем текстовую альтернативу
            email = EmailMessage(
                subject=encoded_subject,
                body=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.encoding = "utf-8"
            email.content_subtype = "html"
            # Добавляем текстовую альтернативу для почтовых клиентов без поддержки HTML
            if text_message:
                email.attach_alternative(text_message, "text/plain; charset=UTF-8")
        else:
            # Если только текстовая версия
            email = EmailMessage(
                subject=encoded_subject,
                body=text_message or "",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.encoding = "utf-8"

        # Устанавливаем дополнительные заголовки для правильной кодировки
        # Это критично для старых почтовых клиентов
        email.extra_headers = email.extra_headers or {}
        if html_message:
            email.extra_headers["Content-Type"] = "text/html; charset=UTF-8"
        else:
            email.extra_headers["Content-Type"] = "text/plain; charset=UTF-8"
        email.extra_headers["Content-Transfer-Encoding"] = "8bit"
        # Явно указываем кодировку для MIME
        email.extra_headers["MIME-Version"] = "1.0"

        email.send(fail_silently=False)

        # Отмечаем уведомление как отправленное
        notification.mark_as_sent()

        return (
            f"Email sent to user {user.username} for order {notification.order.title}"
        )

    except Exception as e:
        # Логируем ошибку
        import logging

        logger = logging.getLogger("orders")
        logger.error(
            f"Ошибка при отправке email для уведомления {notification_id}: {str(e)}"
        )

        # Retry при временных ошибках
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2**self.request.retries))

        return f"Error sending email after {self.max_retries} attempts: {str(e)}"


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_overdue_orders(self):
    """Проверка просроченных заказов и отправка напоминаний"""
    try:
        now = timezone.now()
        notifications_sent = 0

        # Получаем все заказы, которые нуждаются в напоминаниях
        # Используем настройки пользователя для определения периода
        overdue_orders = Order.objects.filter(
            models.Q(
                status="uploaded",
                uploaded_at__lte=now
                - timedelta(days=TimeConstants.MIN_REMINDER_DAYS),  # Минимум 1 день
            )
            | models.Q(
                status="sent",
                sent_at__lte=now
                - timedelta(days=TimeConstants.MIN_REMINDER_DAYS),  # Минимум 1 день
            )
        ).select_related("employee", "factory")

        for order in overdue_orders:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-24: Проверяем наличие employee у заказа
            if not order.employee:
                continue

            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-20: Проверяем наличие email адреса у пользователя
            if not order.employee.email:
                continue

            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-23: Используем get_or_create() для предотвращения race condition
            settings_obj, created = NotificationSettings.objects.get_or_create(
                user=order.employee
            )

            if not settings_obj.email_notifications:
                continue

            # Определяем тип уведомления
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к factory.name
            factory_name = order.factory.name if order.factory else "Без фабрики"
            if order.status == "uploaded" and settings_obj.notify_uploaded_reminder:
                notification_type = "uploaded_reminder"
                title = f"Reminder: Order '{order.title}' not sent for {order.days_since_upload} days"
                message = f"Order '{order.title}' for factory '{factory_name}' was uploaded {order.days_since_upload} days ago but has not been sent yet. Please send the order to the factory."
            elif order.status == "sent" and settings_obj.notify_sent_reminder:
                notification_type = "sent_reminder"
                title = f"Reminder: Order '{order.title}' sent but invoice not received for {order.days_since_sent} days"
                message = f"Order '{order.title}' for factory '{factory_name}' was sent {order.days_since_sent} days ago but the invoice has not been received yet. Please contact the factory."
            else:
                continue

            # Проверяем, не отправляли ли мы уже напоминание недавно
            last_reminder = Notification.objects.filter(
                user=order.employee,
                order=order,
                notification_type=notification_type,
                created_at__gte=now - timedelta(days=settings_obj.reminder_frequency),
            ).first()

            if last_reminder:
                continue

            # Создаем уведомление
            notification = Notification.objects.create(
                user=order.employee,
                order=order,
                notification_type=notification_type,
                title=title,
                message=message,
            )

            # Отправляем email асинхронно
            send_notification_email.delay(notification.id)
            notifications_sent += 1

        return f"Sent {notifications_sent} reminders about overdue orders"

    except Exception as e:
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-22: Добавляем retry механизм для обработки временных ошибок
        import logging

        logger = logging.getLogger("orders")
        logger.error(
            f"Ошибка при проверке просроченных заказов: {str(e)}", exc_info=True
        )

        # Retry при временных ошибках (проблемы с БД, сетью и т.д.)
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2**self.request.retries))

        return (
            f"Error checking overdue orders after {self.max_retries} attempts: {str(e)}"
        )


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def send_order_notification(self, order_id, notification_type):
    """Отправка уведомления о изменении статуса заказа"""
    try:
        order = Order.objects.get(id=order_id)

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-24: Проверяем наличие employee у заказа
        if not order.employee:
            return f"Order {order_id} has no employee assigned"

        user = order.employee

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-19: Проверяем наличие email адреса у пользователя
        if not user.email:
            return (
                f"User {user.username} has no email address. Cannot send notification."
            )

        # Проверяем настройки пользователя
        try:
            settings_obj = NotificationSettings.objects.get(user=user)
            if not settings_obj.email_notifications:
                return f"Email notifications disabled for user {user.username}"
        except NotificationSettings.DoesNotExist:
            settings_obj = NotificationSettings.objects.create(user=user)

        # Определяем заголовок и сообщение в зависимости от типа
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к factory.name
        factory_name = order.factory.name if order.factory else "Без фабрики"
        if notification_type == "order_uploaded":
            title = f"Order '{order.title}' uploaded"
            message = f"Order '{order.title}' for factory '{factory_name}' has been successfully uploaded. Please don't forget to send it to the factory."
        elif notification_type == "order_sent":
            if not settings_obj.notify_invoice_received:
                return "Order sent notifications are disabled"
            title = f"Order '{order.title}' sent to factory"
            message = f"Order '{order.title}' has been successfully sent to factory '{factory_name}'. Please wait for the invoice from the factory."
        elif notification_type == "invoice_received":
            if not settings_obj.notify_invoice_received:
                return "Invoice received notifications are disabled"
            title = f"Invoice received for order '{order.title}'"
            message = f"Invoice for order '{order.title}' from factory '{factory_name}' has been successfully received and attached to the order."
        elif notification_type == "payment_received":
            if not settings_obj.notify_invoice_received:
                return "Payment received notifications are disabled"
            title = f"Payment received for order '{order.title}'"
            message = f"New payment for order '{order.title}' from factory '{factory_name}' has been successfully added."
        elif notification_type == "order_completed":
            title = f"Order '{order.title}' completed"
            message = f"Order '{order.title}' from factory '{factory_name}' has been successfully completed."
        else:
            return f"Unknown notification type: {notification_type}"

        # Создаем уведомление
        notification = Notification.objects.create(
            user=user,
            order=order,
            notification_type=notification_type,
            title=title,
            message=message,
        )

        # Отправляем email асинхронно
        send_notification_email.delay(notification.id)

        return f"Notification sent to user {user.username} for order {order.title}"

    except Order.DoesNotExist:
        return f"Order with ID {order_id} not found"
    except Exception as e:
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-22: Добавляем retry механизм для обработки временных ошибок
        import logging

        logger = logging.getLogger("orders")
        logger.error(
            f"Ошибка при отправке уведомления для заказа {order_id}: {str(e)}",
            exc_info=True,
        )

        # Retry при временных ошибках (проблемы с БД, сетью и т.д.)
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2**self.request.retries))

        return f"Error sending notification after {self.max_retries} attempts: {str(e)}"


@shared_task
def create_default_notification_templates():
    """Создание шаблонов уведомлений по умолчанию"""
    templates_data = [
        {
            "template_type": "uploaded_reminder",
            "subject": "Reminder: Order not sent",
            "html_template": """
            <h2>Reminder: Order not sent</h2>
            <p>Hello, {{ user.first_name|default:user.username }}!</p>
            <p>Order <strong>{{ order.title }}</strong> for factory <strong>{{ order.factory.name }}</strong> was uploaded {{ order.days_since_upload }} days ago but has not been sent yet.</p>
            <p>Please send the order to the factory as soon as possible.</p>
            <p><a href="{{ order.get_absolute_url }}">View Order</a></p>
            """,
            "text_template": """
            Reminder: Order not sent
            
            Hello, {{ user.first_name|default:user.username }}!
            
            Order "{{ order.title }}" for factory "{{ order.factory.name }}" was uploaded {{ order.days_since_upload }} days ago but has not been sent yet.
            
            Please send the order to the factory as soon as possible.
            """,
        },
        {
            "template_type": "sent_reminder",
            "subject": "Reminder: Invoice expected",
            "html_template": """
            <h2>Reminder: Order without invoice</h2>
            <p>Hello, {{ user.first_name|default:user.username }}!</p>
            <p>Order <strong>{{ order.title }}</strong> for factory <strong>{{ order.factory.name }}</strong> was sent {{ order.days_since_sent }} days ago but the invoice has not been received yet.</p>
            <p>Please contact the factory to check the order status.</p>
            <p><a href="{{ order.get_absolute_url }}">View Order</a></p>
            """,
            "text_template": """
            Reminder: Order without invoice
            
            Hello, {{ user.first_name|default:user.username }}!
            
            Order "{{ order.title }}" for factory "{{ order.factory.name }}" was sent {{ order.days_since_sent }} days ago but the invoice has not been received yet.
            
            Please contact the factory to check the order status.
            """,
        },
        {
            "template_type": "invoice_received",
            "subject": "Invoice received",
            "html_template": """
            <h2>Invoice received</h2>
            <p>Hello, {{ user.first_name|default:user.username }}!</p>
            <p>Invoice for order <strong>{{ order.title }}</strong> from factory <strong>{{ order.factory.name }}</strong> has been successfully received and attached to the order.</p>
            <p><a href="{{ order.get_absolute_url }}">View Order</a></p>
            """,
            "text_template": """
            Invoice received
            
            Hello, {{ user.first_name|default:user.username }}!
            
            Invoice for order "{{ order.title }}" from factory "{{ order.factory.name }}" has been successfully received and attached to the order.
            """,
        },
        {
            "template_type": "payment_received",
            "subject": "Payment received",
            "html_template": """
            <h2>Payment received</h2>
            <p>Hello, {{ user.first_name|default:user.username }}!</p>
            <p>New payment for order <strong>{{ order.title }}</strong> from factory <strong>{{ order.factory.name }}</strong> has been successfully added.</p>
            <p><a href="{{ order.get_absolute_url }}">View Order</a></p>
            """,
            "text_template": """
            Payment received
            
            Hello, {{ user.first_name|default:user.username }}!
            
            New payment for order "{{ order.title }}" from factory "{{ order.factory.name }}" has been successfully added.
            """,
        },
    ]

    created_count = 0
    for template_data in templates_data:
        template, created = NotificationTemplate.objects.get_or_create(
            template_type=template_data["template_type"], defaults=template_data
        )
        if created:
            created_count += 1

    return f"Created {created_count} notification templates"


@shared_task
def cleanup_old_notifications():
    """Очистка старых уведомлений (старше 30 дней)"""
    from datetime import timedelta

    cutoff_date = timezone.now() - timedelta(days=TimeConstants.METRICS_RETENTION_DAYS)
    old_notifications = Notification.objects.filter(
        created_at__lt=cutoff_date, is_read=True  # Удаляем только прочитанные
    )

    count = old_notifications.count()
    old_notifications.delete()

    return f"Deleted {count} old notifications"


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
        "date": yesterday.date(),
        "total_orders": Order.objects.filter(
            uploaded_at__date=yesterday.date()
        ).count(),
        "new_orders": Order.objects.filter(uploaded_at__date=yesterday.date()).count(),
        "completed_orders": Order.objects.filter(
            completed_at__date=yesterday.date()
        ).count(),
        "overdue_orders": Order.objects.filter(
            Q(
                status="uploaded",
                uploaded_at__lte=now - timedelta(days=TimeConstants.LOG_RETENTION_DAYS),
            )
            | Q(
                status="sent",
                sent_at__lte=now - timedelta(days=TimeConstants.LOG_RETENTION_DAYS),
            )
        ).count(),
        "active_users": User.objects.filter(last_login__date=yesterday.date()).count(),
        "notifications_sent": Notification.objects.filter(
            created_at__date=yesterday.date()
        ).count(),
    }

    # Логируем статистику
    import logging

    logger = logging.getLogger("orders")
    logger.info(f"Daily statistics for {yesterday.date()}: {stats}")

    return f"Generated statistics for {yesterday.date()}: {stats['total_orders']} orders, {stats['completed_orders']} completed"


@shared_task
def check_overdue_payments():
    """Проверка просроченных платежей и отправка уведомлений"""
    now = timezone.now()
    notifications_sent = 0

    # Получаем все просроченные инвойсы
    overdue_invoices = Invoice.objects.filter(
        status="overdue", due_date__lt=now.date()
    ).select_related("order", "order__employee", "order__factory")

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
            notification_type="payment_overdue",
            created_at__gte=now - timedelta(days=settings_obj.reminder_frequency),
        ).first()

        if last_reminder:
            continue

        # Создаем уведомление
        days_overdue = (now.date() - invoice.due_date).days
        title = f"Overdue payment: Invoice {invoice.invoice_number}"
        message = f"Invoice {invoice.invoice_number} for order '{invoice.order.title}' is overdue by {days_overdue} days. Remaining amount: {invoice.remaining_amount}€"

        notification = Notification.objects.create(
            user=user,
            order=invoice.order,
            notification_type="payment_overdue",
            title=title,
            message=message,
        )

        # Отправляем email асинхронно
        send_notification_email.delay(notification.id)
        notifications_sent += 1

    return f"Sent {notifications_sent} notifications about overdue payments"
