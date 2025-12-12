from celery import shared_task
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from django.utils.html import escape
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
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


@shared_task(bind=True, max_retries=3, default_retry_delay=60)
def check_missing_invoices_for_factories(self):
    """
    Проверка заказов без инвойсов и отправка напоминаний фабрикам.
    
    Проверяет заказы, которые были отправлены фабрике более 5 дней назад,
    но инвойс еще не загружен. Отправляет напоминание на email фабрики.
    """
    try:
        now = timezone.now()
        reminders_sent = 0
        
        # Получаем заказы, которые были отправлены более 5 дней назад
        # и у которых нет инвойса (нет invoice_file и нет Invoice объекта)
        cutoff_date = now - timedelta(days=TimeConstants.INVOICE_REMINDER_DAYS)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-76: Проверяем что sent_at не None
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-77: Фильтруем только активные фабрики
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-82: Используем prefetch_related для оптимизации запросов
        # Используем Exists для эффективной проверки наличия Invoice
        from django.db.models import Exists, OuterRef
        
        # Подзапрос для проверки наличия Invoice
        invoice_exists = Invoice.objects.filter(order_id=OuterRef('pk'))
        
        orders_without_invoice = Order.objects.filter(
            status='sent',
            sent_at__isnull=False,  # BUG-76: Проверяем что sent_at не None
            sent_at__lte=cutoff_date,
            invoice_file__isnull=True,
            cancelled_by_client=False,
            factory__is_active=True,  # BUG-77: Только активные фабрики
        ).select_related('factory', 'factory__country', 'employee').annotate(
            has_invoice=Exists(invoice_exists)
        ).filter(has_invoice=False)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-75 и BUG-82: Теперь все заказы без Invoice уже отфильтрованы
        orders_to_remind = list(orders_without_invoice)
        
        for order in orders_to_remind:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверки уже выполнены в фильтре, но оставляем для безопасности
            if not order.factory:
                continue
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-77: Дополнительная проверка is_active
            if not order.factory.is_active:
                import logging
                logger = logging.getLogger('orders')
                logger.warning(
                    f'Factory {order.factory.name} (ID: {order.factory.id}) is not active. '
                    f'Skipping reminder for order {order.id}.'
                )
                continue
            
            if not order.factory.email:
                import logging
                logger = logging.getLogger('orders')
                logger.warning(
                    f'Factory {order.factory.name} (ID: {order.factory.id}) has no email address. '
                    f'Cannot send reminder for order {order.id}.'
                )
                continue
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-78: Проверяем наличие employee
            if not order.employee:
                import logging
                logger = logging.getLogger('orders')
                logger.warning(
                    f'Order {order.id} has no employee assigned. '
                    f'Cannot send reminder.'
                )
                continue
            
            # Проверяем, не отправляли ли мы уже напоминание недавно
            if order.last_factory_reminder_sent:
                days_since_last_reminder = (
                    now - order.last_factory_reminder_sent
                ).days
                if days_since_last_reminder < TimeConstants.FACTORY_REMINDER_FREQUENCY:
                    continue
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-79 и BUG-80: Используем транзакцию и повторную проверку Invoice
            # для предотвращения race condition и дублирования напоминаний
            from django.db import transaction
            
            try:
                with transaction.atomic():
                    # Блокируем заказ для обновления и повторно проверяем все условия
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-97: Используем select_related для factory чтобы избежать дополнительных запросов
                    try:
                        order = Order.objects.select_for_update().select_related('factory').get(pk=order.pk)
                    except Order.DoesNotExist:
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-97: Заказ был удален между проверкой и блокировкой
                        import logging
                        logger = logging.getLogger('orders')
                        logger.warning(f'Order {order.pk} was deleted before reminder could be sent. Skipping.')
                        continue
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-93: Проверяем cancelled_by_client после блокировки
                    if order.cancelled_by_client:
                        import logging
                        logger = logging.getLogger('orders')
                        logger.info(
                            f'Order {order.id} was cancelled by client before reminder could be sent. '
                            f'Skipping reminder.'
                        )
                        continue
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-95: Проверяем status после блокировки
                    if order.status != 'sent':
                        import logging
                        logger = logging.getLogger('orders')
                        logger.info(
                            f'Order {order.id} status changed to {order.status} before reminder could be sent. '
                            f'Skipping reminder.'
                        )
                        continue
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-96: Проверяем sent_at после блокировки
                    if not order.sent_at or order.sent_at > cutoff_date:
                        import logging
                        logger = logging.getLogger('orders')
                        logger.info(
                            f'Order {order.id} sent_at changed or is None before reminder could be sent. '
                            f'Skipping reminder.'
                        )
                        continue
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-94: Проверяем factory__is_active после блокировки
                    if not order.factory or not order.factory.is_active:
                        import logging
                        logger = logging.getLogger('orders')
                        logger.info(
                            f'Order {order.id} factory is not active or missing before reminder could be sent. '
                            f'Skipping reminder.'
                        )
                        continue
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-99: Проверяем invoice_file после блокировки
                    if order.invoice_file:
                        import logging
                        logger = logging.getLogger('orders')
                        logger.info(
                            f'Invoice file was uploaded for order {order.id} before reminder could be sent. '
                            f'Skipping reminder.'
                        )
                        continue
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-88: Используем exists() вместо обращения к order.invoice
                    # для избежания дополнительного запроса к БД и исключения DoesNotExist
                    if Invoice.objects.filter(order_id=order.pk).exists():
                        # Если Invoice существует, пропускаем этот заказ
                        import logging
                        logger = logging.getLogger('orders')
                        logger.info(
                            f'Invoice was created for order {order.id} before reminder could be sent. '
                            f'Skipping reminder.'
                        )
                        continue
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-100: Проверяем email фабрики после блокировки
                    if not order.factory.email:
                        import logging
                        logger = logging.getLogger('orders')
                        logger.warning(
                            f'Factory {order.factory.name} (ID: {order.factory.id}) has no email address. '
                            f'Cannot send reminder for order {order.id}.'
                        )
                        continue
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-101: Проверяем employee после блокировки
                    if not order.employee:
                        import logging
                        logger = logging.getLogger('orders')
                        logger.warning(
                            f'Order {order.id} has no employee assigned. '
                            f'Cannot send reminder.'
                        )
                        continue
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-80 и BUG-90: Проверяем, не было ли уже отправлено напоминание
                    # между проверкой и блокировкой, и проверяем на отрицательное значение
                    if order.last_factory_reminder_sent:
                        days_since_last_reminder = (
                            now - order.last_factory_reminder_sent
                        ).days
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-90: Проверяем на отрицательное значение
                        # (если last_factory_reminder_sent в будущем из-за проблем с часовыми поясами)
                        if days_since_last_reminder < 0:
                            import logging
                            logger = logging.getLogger('orders')
                            logger.warning(
                                f'Order {order.id} has last_factory_reminder_sent in the future. '
                                f'This may indicate a timezone issue. Resetting reminder check.'
                            )
                            # Если дата в будущем, сбрасываем проверку и продолжаем
                        elif days_since_last_reminder < TimeConstants.FACTORY_REMINDER_FREQUENCY:
                            continue
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-91: Обработка исключений при отправке email
                    try:
                        # Отправляем напоминание фабрике
                        send_factory_invoice_reminder(order)
                    except Exception as email_error:
                        import logging
                        logger = logging.getLogger('orders')
                        logger.error(
                            f'Ошибка отправки email напоминания для заказа {order.id}: {str(email_error)}',
                            exc_info=True
                        )
                        # Если отправка не удалась, не обновляем счетчики и не продолжаем транзакцию
                        raise
                    
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-92: Проверка на переполнение factory_reminder_count
                    # PositiveIntegerField имеет максимальное значение 2147483647
                    if order.factory_reminder_count >= 2147483647:
                        import logging
                        logger = logging.getLogger('orders')
                        logger.warning(
                            f'Order {order.id} has reached maximum factory_reminder_count. '
                            f'Not incrementing further.'
                        )
                    else:
                        order.factory_reminder_count += 1
                    
                    # Обновляем поля напоминания в той же транзакции
                    order.last_factory_reminder_sent = now
                    order.save(update_fields=['last_factory_reminder_sent', 'factory_reminder_count'])
                    
                    reminders_sent += 1
                
            except Exception as e:
                import logging
                logger = logging.getLogger('orders')
                logger.error(
                    f'Ошибка при отправке напоминания фабрике для заказа {order.id}: {str(e)}',
                    exc_info=True
                )
                # Продолжаем обработку других заказов
                continue
        
        return f"Sent {reminders_sent} invoice reminders to factories"
    
    except Exception as e:
        import logging
        logger = logging.getLogger('orders')
        logger.error(
            f'Ошибка при проверке заказов без инвойсов: {str(e)}',
            exc_info=True
        )
        
        # Retry при временных ошибках
        if self.request.retries < self.max_retries:
            raise self.retry(countdown=60 * (2 ** self.request.retries))
        
        return f"Error checking missing invoices after {self.max_retries} attempts: {str(e)}"


def send_factory_invoice_reminder(order):
    """
    Отправка email напоминания фабрике о необходимости загрузить инвойс.
    
    Использует шаблоны из базы данных (EmailTemplate с типом 'invoice_request'),
    если они доступны. В противном случае использует встроенные шаблоны как fallback.
    
    Args:
        order: Order instance
        
    Raises:
        ValueError: Если фабрика или email не указаны
        Exception: При ошибке отправки email
    """
    if not order.factory:
        raise ValueError('Заказ не имеет привязанной фабрики!')
    
    if not order.factory.email:
        raise ValueError('У фабрики не указан email адрес!')
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-87: Валидация email адреса
    try:
        validate_email(order.factory.email)
    except ValidationError:
        raise ValueError(f'Невалидный email адрес фабрики: {order.factory.email}')
    
    # Определяем язык email на основе страны фабрики
    from .email_utils import get_language_by_country_code, get_email_template_from_db
    
    country_code = order.factory.country.code if (
        order.factory and order.factory.country
    ) else None
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-85: Согласованность fallback языка
    # get_language_by_country_code возвращает 'ru' по умолчанию, используем тот же fallback
    if not country_code:
        language_code = 'ru'  # По умолчанию русский (как в get_language_by_country_code)
    else:
        language_code = get_language_by_country_code(country_code)
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-81: Проверяем что sent_at не None перед использованием
    if not order.sent_at:
        raise ValueError('Заказ не имеет даты отправки (sent_at). Невозможно отправить напоминание.')
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-89: Явная проверка days_since_sent на None
    # days_since_sent может вернуть None только если sent_at is None, что мы уже проверили
    # Но для безопасности явно вычисляем значение
    if order.sent_at:
        days_since_sent = (timezone.now() - order.sent_at).days
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем на отрицательное значение (если sent_at в будущем)
        if days_since_sent < 0:
            days_since_sent = 0
    else:
        # Это не должно произойти, так как мы проверили выше, но для безопасности
        days_since_sent = 0
    
    # Получаем шаблон из базы данных
    template = get_email_template_from_db('invoice_request', language_code)
    template_used = None  # Будет установлено в 'database' или 'built-in'
    
    if template:
        # Используем шаблон из базы данных
        import logging
        logger = logging.getLogger('orders')
        logger.info(
            f'Using database template: {template.name} (ID: {template.id}) '
            f'for invoice reminder to factory {order.factory.email} (order {order.id})'
        )
        
        # Формируем контекст для шаблона
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-78: Безопасный доступ к employee.get_full_name()
        factory_name = order.factory.name if order.factory else "Unknown Factory"
        if order.employee:
            employee_name = order.employee.get_full_name() or order.employee.username
        else:
            employee_name = "Unknown Employee"
        
        context = {
            'order': order,
            'factory': order.factory if order.factory else None,
            'employee': order.employee,
            'country': order.factory.country if (order.factory and order.factory.country) else None,
            'days_since_sent': days_since_sent,
            'factory_name': factory_name,
            'employee_name': employee_name,
        }
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-103: Проверяем что шаблон все еще активен перед использованием
        # Шаблон мог быть деактивирован между получением и использованием
        from .models import EmailTemplate
        try:
            # Перезагружаем шаблон из БД для проверки актуального состояния
            template_check = EmailTemplate.objects.get(pk=template.pk)
            if not template_check.is_active:
                import logging
                logger = logging.getLogger('orders')
                logger.warning(
                    f'Template {template.name} (ID: {template.id}) was deactivated before use. '
                    f'Falling back to built-in templates for order {order.id}'
                )
                template = None
                template_rendered = False
        except EmailTemplate.DoesNotExist:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-102: Шаблон был удален между получением и использованием
            import logging
            logger = logging.getLogger('orders')
            logger.warning(
                f'Template {template.name} (ID: {template.id}) was deleted before use. '
                f'Falling back to built-in templates for order {order.id}'
            )
            template = None
            template_rendered = False
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-84: Обработка ошибок при рендеринге шаблона
        template_rendered = False
        if template:
            try:
                # Рендерим шаблон
                rendered = template.render_template(context)
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-104: Проверяем что rendered содержит все необходимые ключи
                required_keys = ['subject', 'html_content', 'text_content']
                missing_keys = [key for key in required_keys if key not in rendered]
                if missing_keys:
                    raise ValueError(f'Template rendered result is missing required keys: {missing_keys}')
                
                subject = rendered['subject']
                html_message = rendered['html_content']
                text_message = rendered['text_content']
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-102: Обработка ошибок при mark_as_used
                try:
                    # Отмечаем шаблон как использованный
                    template.mark_as_used()
                    logger.info(f'Template {template.name} marked as used')
                except Exception as mark_error:
                    # Если не удалось отметить как использованный, логируем но продолжаем
                    logger.warning(
                        f'Failed to mark template {template.name} (ID: {template.id}) as used: {str(mark_error)}'
                    )
                
                template_rendered = True
                template_used = 'database'
            except (ValueError, Exception) as e:
                # Если ошибка рендеринга, используем fallback шаблоны
                logger.error(
                    f'Error rendering template {template.name} (ID: {template.id}): {str(e)}. '
                    f'Falling back to built-in templates for order {order.id}',
                    exc_info=True
                )
                template_rendered = False
    
    if not template or not template_rendered:
        # Fallback к встроенным шаблонам
        import logging
        logger = logging.getLogger('orders')
        if not template:
            logger.warning(
                f'No database template found for invoice_request (language: {language_code}), '
                f'using built-in templates for order {order.id}'
            )
        else:
            logger.warning(
                f'Database template found but rendering failed, '
                f'using built-in templates for order {order.id}'
            )
        template_used = 'built-in'
        
        # Формируем subject и сообщение
        from email.header import Header
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-106: Проверка на None для order.title
        order_title = order.title if order.title else "Без названия"
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-86: Экранирование HTML для безопасности
        # Экранируем данные перед вставкой в HTML шаблоны
        safe_order_title = escape(order_title)
        safe_factory_name = escape(order.factory.name if order.factory else "Unknown Factory")
        if order.employee:
            safe_employee_name = escape(order.employee.get_full_name() or order.employee.username)
        else:
            safe_employee_name = "Unknown Employee"
        
        # Базовый subject на разных языках (subject не требует экранирования, т.к. это plain text)
        subject_templates = {
            'ru': f'Напоминание: Инвойс для заказа "{order_title}"',
            'en': f'Reminder: Invoice for order "{order_title}"',
            'de': f'Erinnerung: Rechnung für Bestellung "{order_title}"',
            'tr': f'Hatırlatma: "{order_title}" siparişi için fatura',
            'it': f'Promemoria: Fattura per ordine "{order_title}"',
        }
        subject = subject_templates.get(language_code, subject_templates['en'])
        
        # Формируем HTML сообщение
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-83: Безопасный доступ к employee
        factory_name = safe_factory_name
        employee_name = safe_employee_name
        
        # Базовые шаблоны сообщений на разных языках
        html_templates = {
            'ru': f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #2c3e50;">Напоминание о загрузке инвойса</h2>
                <p>Уважаемая фабрика <strong>{factory_name}</strong>,</p>
                <p>Напоминаем вам, что заказ <strong>"{safe_order_title}"</strong> был отправлен вам {days_since_sent} дней назад, но инвойс еще не был загружен в систему.</p>
                <p>Пожалуйста, загрузите инвойс как можно скорее.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p><strong>Детали заказа:</strong></p>
                <ul>
                    <li><strong>Название заказа:</strong> {safe_order_title}</li>
                    <li><strong>Дата отправки:</strong> {order.sent_at.strftime('%d.%m.%Y %H:%M') if order.sent_at else 'Не указана'}</li>
                    <li><strong>Количество дней с момента отправки:</strong> {days_since_sent}</li>
                    <li><strong>Ответственный сотрудник:</strong> {employee_name}</li>
                </ul>
                <p>С уважением,<br>XXL OrderHub System</p>
            </body>
            </html>
            """,
            'en': f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #2c3e50;">Invoice Upload Reminder</h2>
                <p>Dear Factory <strong>{factory_name}</strong>,</p>
                <p>We remind you that order <strong>"{safe_order_title}"</strong> was sent to you {days_since_sent} days ago, but the invoice has not yet been uploaded to the system.</p>
                <p>Please upload the invoice as soon as possible.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p><strong>Order Details:</strong></p>
                <ul>
                    <li><strong>Order Title:</strong> {safe_order_title}</li>
                    <li><strong>Sent Date:</strong> {order.sent_at.strftime('%d.%m.%Y %H:%M') if order.sent_at else 'Not specified'}</li>
                    <li><strong>Days since sent:</strong> {days_since_sent}</li>
                    <li><strong>Responsible Employee:</strong> {employee_name}</li>
                </ul>
                <p>Best regards,<br>XXL OrderHub System</p>
            </body>
            </html>
            """,
            'de': f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #2c3e50;">Erinnerung zur Rechnungs-Upload</h2>
                <p>Liebe Fabrik <strong>{factory_name}</strong>,</p>
                <p>Wir erinnern Sie daran, dass die Bestellung <strong>"{safe_order_title}"</strong> vor {days_since_sent} Tagen an Sie gesendet wurde, aber die Rechnung noch nicht in das System hochgeladen wurde.</p>
                <p>Bitte laden Sie die Rechnung so bald wie möglich hoch.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p><strong>Bestelldetails:</strong></p>
                <ul>
                    <li><strong>Bestellungstitel:</strong> {safe_order_title}</li>
                    <li><strong>Versanddatum:</strong> {order.sent_at.strftime('%d.%m.%Y %H:%M') if order.sent_at else 'Nicht angegeben'}</li>
                    <li><strong>Tage seit Versand:</strong> {days_since_sent}</li>
                    <li><strong>Verantwortlicher Mitarbeiter:</strong> {employee_name}</li>
                </ul>
                <p>Mit freundlichen Grüßen,<br>XXL OrderHub System</p>
            </body>
            </html>
            """,
            'tr': f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2 style="color: #2c3e50;">Fatura Yükleme Hatırlatması</h2>
                <p>Sayın Fabrika <strong>{factory_name}</strong>,</p>
                <p>Size <strong>"{safe_order_title}"</strong> siparişinin {days_since_sent} gün önce gönderildiğini, ancak faturanın henüz sisteme yüklenmediğini hatırlatıyoruz.</p>
                <p>Lütfen faturanızı en kısa sürede yükleyin.</p>
                <hr style="border: none; border-top: 1px solid #eee; margin: 20px 0;">
                <p><strong>Sipariş Detayları:</strong></p>
                <ul>
                    <li><strong>Sipariş Başlığı:</strong> {safe_order_title}</li>
                    <li><strong>Gönderim Tarihi:</strong> {order.sent_at.strftime('%d.%m.%Y %H:%M') if order.sent_at else 'Belirtilmemiş'}</li>
                    <li><strong>Gönderimden bu yana geçen günler:</strong> {days_since_sent}</li>
                    <li><strong>Sorumlu Çalışan:</strong> {employee_name}</li>
                </ul>
                <p>Saygılarımızla,<br>XXL OrderHub System</p>
            </body>
            </html>
            """,
        }
        
        html_message = html_templates.get(language_code, html_templates['en'])
        
        # Формируем текстовую версию (упрощенную)
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-106: Используем order_title вместо order.title
        text_message = f"""
Invoice Upload Reminder

Dear Factory {factory_name},

We remind you that order "{order_title}" was sent to you {days_since_sent} days ago, but the invoice has not yet been uploaded to the system.

Please upload the invoice as soon as possible.

Order Details:
- Order Title: {order_title}
- Sent Date: {order.sent_at.strftime('%d.%m.%Y %H:%M') if order.sent_at else 'Not specified'}
- Days since sent: {days_since_sent}
- Responsible Employee: {employee_name}

Best regards,
XXL OrderHub System
        """.strip()
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-105: Убеждаемся что template_used установлен
    if template_used is None:
        template_used = 'unknown'
        import logging
        logger = logging.getLogger('orders')
        logger.warning(
            f'template_used was not set for order {order.id}. This should not happen.'
        )
    
    # Кодируем subject для не-ASCII символов
    from email.header import Header
    try:
        subject.encode('ascii')
        encoded_subject = subject
    except UnicodeEncodeError:
        encoded_subject = str(Header(subject, 'utf-8'))
    except (AttributeError, UnicodeDecodeError):
        encoded_subject = subject
    
    # Отправляем email
    email = EmailMessage(
        subject=encoded_subject,
        body=html_message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[order.factory.email],
    )
    email.content_subtype = "html"
    email.encoding = 'utf-8'
    
    # Устанавливаем дополнительные заголовки для правильной кодировки
    email.extra_headers = email.extra_headers or {}
    email.extra_headers["Content-Type"] = "text/html; charset=UTF-8"
    email.extra_headers["Content-Transfer-Encoding"] = "8bit"
    email.extra_headers["MIME-Version"] = "1.0"
    
    # Добавляем текстовую альтернативу для почтовых клиентов без поддержки HTML
    if text_message:
        email.attach_alternative(text_message, "text/plain; charset=UTF-8")
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-91: Обработка исключений при отправке email
    try:
        email.send(fail_silently=False)
    except Exception as email_send_error:
        import logging
        logger = logging.getLogger('orders')
        logger.error(
            f'Ошибка отправки email напоминания для заказа {order.id} '
            f'на адрес {order.factory.email}: {str(email_send_error)}',
            exc_info=True
        )
        raise ValueError(f'Не удалось отправить email: {str(email_send_error)}')
    
    # Логируем успешную отправку
    import logging
    logger = logging.getLogger('orders')
    logger.info(
        f'Invoice reminder email sent to factory {order.factory.email} '
        f'for order {order.id} (days since sent: {days_since_sent}, '
        f'template: {template_used or "unknown"})'
    )
