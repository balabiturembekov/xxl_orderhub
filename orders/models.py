from typing import Optional, Dict, Any, List
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.template.loader import render_to_string
from django.conf import settings
from .validators import validate_excel_file, validate_pdf_file, validate_safe_filename
from .constants import TimeConstants


class UserProfile(models.Model):
    """
    Расширенный профиль пользователя.
    
    Содержит дополнительную информацию о пользователе:
    - Личные данные (имя, фамилия)
    - Контактная информация (телефон)
    - Рабочая информация (отдел, должность)
    - Настройки уведомлений
    """
    user = models.OneToOneField(
        User, 
        on_delete=models.CASCADE, 
        verbose_name="Пользователь",
        related_name='profile'
    )
    first_name = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Имя"
    )
    last_name = models.CharField(
        max_length=50, 
        blank=True, 
        verbose_name="Фамилия"
    )
    phone = models.CharField(
        max_length=20, 
        blank=True, 
        verbose_name="Телефон"
    )
    department = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Отдел"
    )
    position = models.CharField(
        max_length=100, 
        blank=True, 
        verbose_name="Должность"
    )
    created_at = models.DateTimeField(
        auto_now_add=True, 
        verbose_name="Дата создания профиля"
    )
    updated_at = models.DateTimeField(
        auto_now=True, 
        verbose_name="Дата обновления профиля"
    )
    
    class Meta:
        verbose_name = "Профиль пользователя"
        verbose_name_plural = "Профили пользователей"
        ordering = ['user__username']
    
    def __str__(self):
        return f"Профиль {self.user.username}"
    
    @property
    def full_name(self):
        """
        Возвращает полное имя пользователя.
        
        Returns:
            str: Полное имя или username, если имя не указано
        """
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        elif self.first_name:
            return self.first_name
        elif self.last_name:
            return self.last_name
        else:
            return self.user.username
    
    @property
    def display_name(self):
        """
        Возвращает отображаемое имя пользователя.
        
        Returns:
            str: Полное имя или username
        """
        return self.full_name


class Country(models.Model):
    """Модель для стран"""
    name = models.CharField(max_length=100, verbose_name="Название страны")
    code = models.CharField(max_length=3, unique=True, verbose_name="Код страны")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Страна"
        verbose_name_plural = "Страны"
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Factory(models.Model):
    """Модель для фабрик"""
    name = models.CharField(max_length=200, verbose_name="Название фабрики")
    country = models.ForeignKey(Country, on_delete=models.CASCADE, verbose_name="Страна")
    email = models.EmailField(verbose_name="Email для отправки заказов")
    contact_person = models.CharField(max_length=100, blank=True, verbose_name="Контактное лицо")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Телефон")
    address = models.TextField(blank=True, verbose_name="Адрес")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Фабрика"
        verbose_name_plural = "Фабрики"
        ordering = ['country', 'name']
    
    def __str__(self):
        country_name = self.country.name if self.country else "Без страны"
        return f"{self.name} ({country_name})"


class Order(models.Model):
    """Модель для заказов"""
    
    STATUS_CHOICES = [
        ('uploaded', 'Загружен'),
        ('sent', 'Отправлен'),
        ('invoice_received', 'Инвойс получен'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
    ]
    
    title = models.CharField(max_length=200, verbose_name="Название заказа")
    description = models.TextField(blank=True, verbose_name="Описание")
    factory = models.ForeignKey(Factory, on_delete=models.CASCADE, verbose_name="Фабрика")
    employee = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Сотрудник")
    
    # Файлы
    excel_file = models.FileField(
        upload_to='orders/excel/',
        validators=[
            FileExtensionValidator(allowed_extensions=['xlsx', 'xls']),
            validate_excel_file
        ],
        verbose_name="Excel файл заказа"
    )
    invoice_file = models.FileField(
        upload_to='orders/invoices/',
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf']),
            validate_pdf_file
        ],
        blank=True,
        null=True,
        verbose_name="PDF файл инвойса"
    )
    
    # Статус и даты
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='uploaded',
        verbose_name="Статус"
    )
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата загрузки")
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата отправки")
    invoice_received_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата получения инвойса")
    completed_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата завершения")
    
    # Дополнительная информация
    comments = models.TextField(blank=True, verbose_name="Комментарии")
    factory_comments = models.TextField(blank=True, verbose_name="Комментарии фабрики")
    
    # Уведомления
    last_reminder_sent = models.DateTimeField(blank=True, null=True, verbose_name="Последнее напоминание")
    reminder_count = models.PositiveIntegerField(default=0, verbose_name="Количество напоминаний")
    
    # Отмена клиентом
    cancelled_by_client = models.BooleanField(default=False, verbose_name="Отменен клиентом")
    cancelled_by_client_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата отмены клиентом")
    cancelled_by_client_comment = models.TextField(blank=True, verbose_name="Комментарий при отмене клиентом")
    cancelled_by_client_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='cancelled_orders',
        verbose_name="Отменил клиентом"
    )
    
    # Тип фактуры для турецких фабрик (TR)
    factura_export = models.BooleanField(default=False, verbose_name="Factura Export")
    e_factura_turkey = models.BooleanField(default=False, verbose_name="E-Factura Turkey")
    
    @property
    def is_turkish_factory(self):
        """Проверка, является ли фабрика турецкой"""
        return self.factory and self.factory.country and self.factory.country.code == 'TR'
    
    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-uploaded_at']
        indexes = [
            models.Index(fields=['cancelled_by_client'], name='order_cancelled_idx'),
            models.Index(fields=['cancelled_by_client_at'], name='order_cancelled_at_idx'),
            models.Index(fields=['cancelled_by_client', 'cancelled_by_client_at'], name='order_cancelled_comp_idx'),
        ]
    
    def __str__(self):
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к factory.name
        factory_name = self.factory.name if self.factory else "Без фабрики"
        return f"{self.title} - {factory_name}"
    
    @property
    def days_since_upload(self):
        """Количество дней с момента загрузки"""
        return (timezone.now() - self.uploaded_at).days
    
    @property
    def days_since_sent(self):
        """Количество дней с момента отправки"""
        if self.sent_at:
            return (timezone.now() - self.sent_at).days
        return None
    
    @property
    def needs_reminder(self):
        """Нужно ли отправить напоминание"""
        if self.status == 'uploaded' and self.days_since_upload >= 7:
            return True
        elif self.status == 'sent' and self.days_since_sent and self.days_since_sent >= 7:
            return True
        return False
    
    def mark_as_sent(self):
        """Отметить заказ как отправленный"""
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-29: Проверяем валидность перехода статуса
        if self.status != 'uploaded':
            raise ValueError(f'Нельзя отметить как отправленный заказ со статусом {self.status}. Ожидается статус "uploaded".')
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()
    
    def mark_invoice_received(self, invoice_file):
        """Отметить получение инвойса"""
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-29: Проверяем валидность перехода статуса
        if self.status != 'sent':
            raise ValueError(f'Нельзя отметить получение инвойса для заказа со статусом {self.status}. Ожидается статус "sent".')
        self.status = 'invoice_received'
        self.invoice_file = invoice_file
        self.invoice_received_at = timezone.now()
        self.save()
    
    def mark_as_completed(self):
        """Отметить заказ как завершенный"""
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-29: Проверяем валидность перехода статуса
        if self.status != 'invoice_received':
            raise ValueError(f'Нельзя завершить заказ со статусом {self.status}. Ожидается статус "invoice_received".')
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def clean(self) -> None:
        """Валидация модели"""
        super().clean()

        # Валидация имени файла (только если файл загружен)
        if self.excel_file and hasattr(self.excel_file, 'name') and self.excel_file.name:
            validate_safe_filename(self.excel_file.name)
        if self.invoice_file and hasattr(self.invoice_file, 'name') and self.invoice_file.name:
            validate_safe_filename(self.invoice_file.name)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Валидация полей отмены клиентом
        if self.cancelled_by_client:
            # Если заказ отменен клиентом, должны быть установлены обязательные поля
            if not self.cancelled_by_client_at:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'cancelled_by_client_at': 'Дата отмены должна быть установлена, если заказ отменен клиентом.'
                })
            if not self.cancelled_by_client_by:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'cancelled_by_client_by': 'Пользователь, отменивший заказ, должен быть указан.'
                })
            # Проверка длины комментария (максимум 2000 символов)
            if self.cancelled_by_client_comment and len(self.cancelled_by_client_comment) > 2000:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'cancelled_by_client_comment': 'Комментарий не может быть длиннее 2000 символов.'
                })
        else:
            # Если заказ не отменен, поля отмены должны быть пустыми
            if self.cancelled_by_client_at:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'cancelled_by_client_at': 'Дата отмены не может быть установлена, если заказ не отменен клиентом.'
                })
            if self.cancelled_by_client_by:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'cancelled_by_client_by': 'Пользователь, отменивший заказ, не может быть указан, если заказ не отменен.'
                })
        
        # Валидация типа фактуры для турецких фабрик
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем для статусов 'invoice_received' и 'completed'
        if self.is_turkish_factory and self.status in ['invoice_received', 'completed']:
            if not self.factura_export and not self.e_factura_turkey:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'factura_export': 'Для турецких фабрик необходимо выбрать тип фактуры (Factura Export или E-Factura Turkey).',
                    'e_factura_turkey': 'Для турецких фабрик необходимо выбрать тип фактуры (Factura Export или E-Factura Turkey).'
                })
            if self.factura_export and self.e_factura_turkey:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'factura_export': 'Можно выбрать только один тип фактуры.',
                    'e_factura_turkey': 'Можно выбрать только один тип фактуры.'
                })
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Если заказ не турецкий, поля типа фактуры должны быть False
        elif not self.is_turkish_factory:
            if self.factura_export or self.e_factura_turkey:
                from django.core.exceptions import ValidationError
                raise ValidationError({
                    'factura_export': 'Тип фактуры доступен только для турецких фабрик.',
                    'e_factura_turkey': 'Тип фактуры доступен только для турецких фабрик.'
                })
    
    def get_absolute_url(self) -> str:
        """URL для детальной страницы заказа"""
        from django.urls import reverse
        return reverse('order_detail', kwargs={'pk': self.pk})


class NotificationSettings(models.Model):
    """Настройки уведомлений для пользователя"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    
    # Настройки email уведомлений
    email_notifications = models.BooleanField(default=True, verbose_name="Email уведомления")
    reminder_frequency = models.PositiveIntegerField(
        default=7, 
        verbose_name="Частота напоминаний (дни)",
        help_text="Количество дней между напоминаниями"
    )
    
    # Настройки типов уведомлений
    notify_uploaded_reminder = models.BooleanField(
        default=True, 
        verbose_name="Напоминания о неотправленных заказах",
        help_text="Получать напоминания о заказах, которые загружены но не отправлены"
    )
    notify_sent_reminder = models.BooleanField(
        default=True, 
        verbose_name="Напоминания о заказах без инвойса",
        help_text="Получать напоминания о заказах, которые отправлены но инвойс не получен"
    )
    notify_invoice_received = models.BooleanField(
        default=True, 
        verbose_name="Уведомления о получении инвойса",
        help_text="Получать уведомления когда фабрика загружает инвойс"
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Настройки уведомлений"
        verbose_name_plural = "Настройки уведомлений"
    
    def __str__(self):
        return f"Настройки уведомлений для {self.user.username}"


class Notification(models.Model):
    """Модель для хранения уведомлений"""
    
    NOTIFICATION_TYPES = [
        ('order_uploaded', 'Заказ загружен'),
        ('order_sent', 'Заказ отправлен'),
        ('invoice_received', 'Инвойс получен'),
        ('order_completed', 'Заказ завершен'),
        ('uploaded_reminder', 'Напоминание о неотправленном заказе'),
        ('sent_reminder', 'Напоминание о заказе без инвойса'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name="Заказ")
    notification_type = models.CharField(
        max_length=20,
        choices=NOTIFICATION_TYPES,
        verbose_name="Тип уведомления"
    )
    
    title = models.CharField(max_length=200, verbose_name="Заголовок")
    message = models.TextField(verbose_name="Сообщение")
    
    # Статус уведомления
    is_read = models.BooleanField(default=False, verbose_name="Прочитано")
    is_sent = models.BooleanField(default=False, verbose_name="Отправлено")
    sent_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата отправки")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    read_at = models.DateTimeField(blank=True, null=True, verbose_name="Дата прочтения")
    
    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"
        ordering = ['-created_at']
    
    def __str__(self) -> str:
        return f"{self.title} - {self.user.username}"
    
    def mark_as_read(self) -> None:
        """Отметить уведомление как прочитанное"""
        self.is_read = True
        self.read_at = timezone.now()
        self.save()
    
    def mark_as_sent(self) -> None:
        """Отметить уведомление как отправленное"""
        self.is_sent = True
        self.sent_at = timezone.now()
        self.save()


class NotificationTemplate(models.Model):
    """Шаблоны для уведомлений"""
    
    TEMPLATE_TYPES = [
        ('uploaded_reminder', 'Напоминание о неотправленном заказе'),
        ('sent_reminder', 'Напоминание о заказе без инвойса'),
        ('invoice_received', 'Инвойс получен'),
        ('order_sent', 'Заказ отправлен'),
        ('order_completed', 'Заказ завершен'),
    ]
    
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPES,
        unique=True,
        verbose_name="Тип шаблона"
    )
    
    subject = models.CharField(max_length=200, verbose_name="Тема письма")
    html_template = models.TextField(verbose_name="HTML шаблон")
    text_template = models.TextField(verbose_name="Текстовый шаблон")
    
    is_active = models.BooleanField(default=True, verbose_name="Активен")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        verbose_name = "Шаблон уведомления"
        verbose_name_plural = "Шаблоны уведомлений"
    
    def __str__(self):
        return f"Шаблон: {self.get_template_type_display()}"


class OrderConfirmation(models.Model):
    """Подтверждения критических операций с заказами"""
    
    ACTION_CHOICES = [
        ('send_order', 'Отправка заказа'),
        ('upload_invoice', 'Загрузка инвойса'),
        ('complete_order', 'Завершение заказа'),
        ('cancel_order', 'Отмена заказа'),
        ('delete_order', 'Удаление заказа'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name="Заказ")
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, verbose_name="Действие")
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Запросил")
    confirmed_by = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        related_name='confirmed_actions',
        null=True, 
        blank=True,
        verbose_name="Подтвердил"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Ожидает подтверждения'),
            ('confirmed', 'Подтверждено'),
            ('rejected', 'Отклонено'),
            ('expired', 'Истекло'),
        ],
        default='pending',
        verbose_name="Статус"
    )
    
    # Данные для подтверждения
    confirmation_data = models.JSONField(default=dict, verbose_name="Данные подтверждения")
    comments = models.TextField(blank=True, verbose_name="Комментарии")
    rejection_reason = models.TextField(blank=True, verbose_name="Причина отклонения")
    
    # Временные метки
    requested_at = models.DateTimeField(auto_now_add=True, verbose_name="Запрошено")
    confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Подтверждено")
    expires_at = models.DateTimeField(verbose_name="Истекает", help_text="Автоматически устанавливается при создании")
    
    class Meta:
        verbose_name = "Подтверждение операции"
        verbose_name_plural = "Подтверждения операций"
        ordering = ['-requested_at']
    
    def __str__(self):
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к order.title
        order_title = self.order.title if self.order else "Без заказа"
        return f"{self.get_action_display()} для заказа {order_title}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            from datetime import timedelta
            # Разные сроки для разных операций
            if self.action == 'send_order':
                self.expires_at = timezone.now() + timedelta(hours=TimeConstants.CONFIRMATION_EXPIRATION_HOURS_SEND)  # 3 дня для отправки
            elif self.action == 'upload_invoice':
                self.expires_at = timezone.now() + timedelta(hours=TimeConstants.CONFIRMATION_EXPIRATION_HOURS_INVOICE)  # 2 дня для инвойса
            elif self.action in ['complete_order', 'cancel_order', 'delete_order']:
                self.expires_at = timezone.now() + timedelta(hours=TimeConstants.CONFIRMATION_EXPIRATION_HOURS)  # 1 день для критических
            else:
                self.expires_at = timezone.now() + timedelta(hours=TimeConstants.CONFIRMATION_EXPIRATION_HOURS)  # По умолчанию 1 день
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """Проверка истечения срока подтверждения"""
        return timezone.now() > self.expires_at
    
    def can_be_confirmed_by(self, user):
        """Проверка, может ли пользователь подтвердить операцию"""
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Подтвердить может либо создатель заказа,
        # либо тот, кто создал подтверждение (requested_by)
        # Это позволяет любому пользователю подтвердить операцию, которую он сам инициировал
        return self.order.employee == user or self.requested_by == user
    
    def confirm(self, user, comments=""):
        """Подтверждение операции"""
        if not self.can_be_confirmed_by(user):
            raise ValueError("Пользователь не может подтвердить эту операцию")
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем истечение срока перед подтверждением
        if self.is_expired():
            # Автоматически помечаем как истекшее
            if self.status == 'pending':
                OrderConfirmation.objects.filter(id=self.id, status='pending').update(status='expired')
            raise ValueError("Срок подтверждения истек")
        
        # Атомарное обновление для предотвращения race condition
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Добавляем проверку истечения в фильтр
        updated = OrderConfirmation.objects.filter(
            id=self.id,
            status='pending',
            expires_at__gt=timezone.now()
        ).update(
            status='confirmed',
            confirmed_by=user,
            confirmed_at=timezone.now(),
            comments=comments
        )
        
        if updated == 0:
            # Проверяем причину - может быть истекло или уже обработано
            self.refresh_from_db()
            if self.is_expired() and self.status == 'pending':
                OrderConfirmation.objects.filter(id=self.id, status='pending').update(status='expired')
                raise ValueError("Срок подтверждения истек")
            raise ValueError("Подтверждение уже обработано")
        
        # Обновляем локальный объект
        self.refresh_from_db()
    
    def reject(self, user, reason=""):
        """Отклонение операции"""
        if not self.can_be_confirmed_by(user):
            raise ValueError("Пользователь не может отклонить эту операцию")
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем истечение срока перед отклонением
        if self.is_expired():
            # Автоматически помечаем как истекшее
            if self.status == 'pending':
                OrderConfirmation.objects.filter(id=self.id, status='pending').update(status='expired')
            raise ValueError("Срок подтверждения истек")
        
        # Атомарное обновление для предотвращения race condition
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Добавляем проверку истечения в фильтр
        updated = OrderConfirmation.objects.filter(
            id=self.id,
            status='pending',
            expires_at__gt=timezone.now()
        ).update(
            status='rejected',
            confirmed_by=user,
            confirmed_at=timezone.now(),
            rejection_reason=reason
        )
        
        if updated == 0:
            # Проверяем причину - может быть истекло или уже обработано
            self.refresh_from_db()
            if self.is_expired() and self.status == 'pending':
                OrderConfirmation.objects.filter(id=self.id, status='pending').update(status='expired')
                raise ValueError("Срок подтверждения истек")
            raise ValueError("Подтверждение уже обработано")
        
        # Обновляем локальный объект
        self.refresh_from_db()


class OrderAuditLog(models.Model):
    """Журнал аудита изменений заказов"""
    
    ACTION_TYPES = [
        ('created', 'Создан'),
        ('updated', 'Обновлен'),
        ('status_changed', 'Изменен статус'),
        ('file_uploaded', 'Загружен файл'),
        ('file_downloaded', 'Скачан файл'),
        ('sent', 'Отправлен'),
        ('completed', 'Завершен'),
        ('cancelled', 'Отменен'),
        ('deleted', 'Удален'),
    ]
    
    order = models.ForeignKey(Order, on_delete=models.CASCADE, verbose_name="Заказ")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    action = models.CharField(max_length=20, choices=ACTION_TYPES, verbose_name="Действие")
    
    # Данные об изменении
    old_value = models.TextField(blank=True, verbose_name="Старое значение")
    new_value = models.TextField(blank=True, verbose_name="Новое значение")
    field_name = models.CharField(max_length=50, blank=True, verbose_name="Поле")
    
    # Метаданные
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP адрес")
    user_agent = models.TextField(blank=True, verbose_name="User Agent")
    comments = models.TextField(blank=True, verbose_name="Комментарии")
    
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Время")
    
    class Meta:
        verbose_name = "Запись аудита"
        verbose_name_plural = "Журнал аудита"
        ordering = ['-timestamp']
    
    def __str__(self):
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к order.title
        order_title = self.order.title if self.order else "Без заказа"
        user_name = self.user.username if self.user else "Без пользователя"
        return f"{self.get_action_display()} заказа {order_title} пользователем {user_name}"
    
    @classmethod
    def log_action(cls, order, user, action, old_value="", new_value="", field_name="", 
                   ip_address=None, user_agent="", comments=""):
        """Создание записи в журнале аудита"""
        return cls.objects.create(
            order=order,
            user=user,
            action=action,
            old_value=old_value,
            new_value=new_value,
            field_name=field_name,
            ip_address=ip_address,
            user_agent=user_agent,
            comments=comments
        )


class EmailTemplate(models.Model):
    """Шаблоны email для отправки заказов фабрикам"""
    
    TEMPLATE_TYPES = [
        ('factory_order', 'Заказ на фабрику'),
        ('order_confirmation', 'Подтверждение заказа'),
        ('order_notification', 'Уведомление о заказе'),
        ('reminder', 'Напоминание'),
        ('confirmation', 'Подтверждение'),
        ('invoice_request', 'Запрос инвойса'),
    ]
    
    LANGUAGE_CHOICES = [
        ('ru', 'Русский'),
        ('en', 'English'),
        ('de', 'Deutsch'),
        ('it', 'Italiano'),
        ('tr', 'Türkçe'),
        ('pl', 'Polski'),
        ('cz', 'Čeština'),
        ('cn', '中文'),
        ('lt', 'Lietuvių'),
    ]
    
    name = models.CharField(
        max_length=100,
        verbose_name="Название шаблона",
        help_text="Удобное название для идентификации шаблона"
    )
    template_type = models.CharField(
        max_length=20,
        choices=TEMPLATE_TYPES,
        default='order_confirmation',
        verbose_name="Тип шаблона"
    )
    language = models.CharField(
        max_length=5,
        choices=LANGUAGE_CHOICES,
        default='ru',
        verbose_name="Язык"
    )
    
    # Содержимое шаблона
    subject = models.CharField(
        max_length=200,
        verbose_name="Тема письма",
        help_text="Используйте переменные: {{ order.title }}, {{ factory.name }}"
    )
    html_content = models.TextField(
        verbose_name="HTML содержимое",
        help_text="HTML версия письма с поддержкой переменных"
    )
    text_content = models.TextField(
        verbose_name="Текстовое содержимое",
        help_text="Текстовая версия письма для клиентов без поддержки HTML"
    )
    
    # Настройки
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
        help_text="Только активные шаблоны используются при отправке"
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name="По умолчанию",
        help_text="Шаблон по умолчанию для данного типа и языка"
    )
    
    # Метаданные
    description = models.TextField(
        blank=True,
        verbose_name="Описание",
        help_text="Описание назначения и особенностей шаблона"
    )
    variables_help = models.TextField(
        blank=True,
        verbose_name="Справка по переменным",
        help_text="Список доступных переменных для использования в шаблоне"
    )
    
    # Аудит
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Создал"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    last_used_at = models.DateTimeField(null=True, blank=True, verbose_name="Последнее использование")
    
    class Meta:
        verbose_name = "Email шаблон"
        verbose_name_plural = "Email шаблоны"
        ordering = ['template_type', 'language', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_language_display()})"
    
    def save(self, *args, **kwargs):
        # Если устанавливаем как шаблон по умолчанию, снимаем флаг с других
        if self.is_default:
            EmailTemplate.objects.filter(
                template_type=self.template_type,
                language=self.language,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)
    
    def get_available_variables(self):
        """Получить список доступных переменных для шаблона"""
        return {
            'order': {
                'title': 'Название заказа',
                'description': 'Описание заказа',
                'uploaded_at': 'Дата заказа',
                'status': 'Статус заказа',
                'comments': 'Комментарии к заказу',
            },
            'factory': {
                'name': 'Название фабрики',
                'email': 'Email фабрики',
                'contact_person': 'Контактное лицо',
                'phone': 'Телефон фабрики',
                'address': 'Адрес фабрики',
            },
            'employee': {
                'get_full_name': 'Полное имя сотрудника',
                'username': 'Имя пользователя',
                'email': 'Email сотрудника',
            },
            'country': {
                'name': 'Название страны',
                'code': 'Код страны',
            }
        }
    
    def render_template(self, context):
        """Рендеринг шаблона с переданным контекстом"""
        from django.template import Template, Context
        from django.template.loader import render_to_string
        
        try:
            # Рендерим HTML версию
            html_template = Template(self.html_content)
            html_rendered = html_template.render(Context(context))
            
            # Рендерим текстовую версию
            text_template = Template(self.text_content)
            text_rendered = text_template.render(Context(context))
            
            return {
                'subject': Template(self.subject).render(Context(context)),
                'html_content': html_rendered,
                'text_content': text_rendered
            }
        except Exception as e:
            raise ValueError(f"Ошибка рендеринга шаблона: {str(e)}")
    
    def get_absolute_url(self):
        """URL для детального просмотра шаблона"""
        from django.urls import reverse
        return reverse('email_template_detail', kwargs={'pk': self.pk})
    
    def mark_as_used(self):
        """Отметить шаблон как использованный"""
        from django.utils import timezone
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])


class EmailTemplateVersion(models.Model):
    """Версии email шаблонов для отслеживания изменений"""
    
    template = models.ForeignKey(
        EmailTemplate,
        on_delete=models.CASCADE,
        related_name='versions',
        verbose_name="Шаблон"
    )
    version_number = models.PositiveIntegerField(verbose_name="Номер версии")
    
    # Содержимое версии
    subject = models.CharField(max_length=200, verbose_name="Тема письма")
    html_content = models.TextField(verbose_name="HTML содержимое")
    text_content = models.TextField(verbose_name="Текстовое содержимое")
    
    # Метаданные версии
    change_description = models.TextField(
        blank=True,
        verbose_name="Описание изменений"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Создал"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Версия шаблона"
        verbose_name_plural = "Версии шаблонов"
        ordering = ['-version_number']
        unique_together = [['template', 'version_number']]
    
    def __str__(self):
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к template.name
        template_name = self.template.name if self.template else "Без шаблона"
        return f"Версия {self.version_number} шаблона {template_name}"


class Invoice(models.Model):
    """
    Модель для инвойсов с детальной информацией о платежах.
    
    Содержит основную информацию об инвойсе:
    - Связь с заказом
    - Уникальный номер инвойса
    - Общая сумма к оплате
    - Статус оплаты
    - Связанные платежи
    """
    
    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Ожидает оплаты'),
        ('partial', 'Частично оплачен'),
        ('paid', 'Полностью оплачен'),
        ('overdue', 'Просрочен'),
    ]
    
    order = models.OneToOneField(
        Order,
        on_delete=models.CASCADE,
        verbose_name="Заказ",
        related_name='invoice'
    )
    invoice_number = models.CharField(
        max_length=100,
        verbose_name="Номер инвойса",
        help_text="Уникальный номер инвойса от фабрики"
    )
    balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Общая сумма к оплате",
        help_text="Полная сумма по инвойсу"
    )
    total_paid = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Сумма всех платежей"
    )
    remaining_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
        verbose_name="Остаток к доплате"
    )
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default='pending',
        verbose_name="Статус оплаты"
    )
    
    # Даты
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    due_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Срок оплаты",
        help_text="Дата, до которой должен быть оплачен инвойс"
    )
    
    # Дополнительная информация
    notes = models.TextField(blank=True, verbose_name="Комментарии")
    
    @property
    def total_cbm(self):
        """Общий объем CBM для заказа (сумма всех записей CBM)"""
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем наличие pk и order перед обращением к связанным объектам
        if not self.pk or not hasattr(self, 'order') or not self.order or not self.order.pk:
            return 0
        from django.db.models import Sum
        try:
            total = self.order.cbm_records.aggregate(
                total=Sum('cbm_value')
            )['total'] or 0
            return total
        except Exception:
            return 0
    
    class Meta:
        verbose_name = "Инвойс"
        verbose_name_plural = "Инвойсы"
        ordering = ['-created_at']
    
    def __str__(self):
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к order.title
        order_title = self.order.title if self.order else "Без заказа"
        return f"Инвойс {self.invoice_number} для заказа {order_title}"
    
    def clean(self):
        """Валидация модели Invoice"""
        from django.core.exceptions import ValidationError
        from django.utils import timezone
        
        super().clean()
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-32: Проверка что due_date не раньше created_at
        if self.due_date and self.created_at:
            if self.due_date < self.created_at.date():
                raise ValidationError({
                    'due_date': 'Срок оплаты не может быть раньше даты создания инвойса.'
                })
        
        # Проверка что balance положительный
        if self.balance is not None and self.balance <= 0:
            raise ValidationError({
                'balance': 'Сумма инвойса должна быть больше нуля.'
            })
    
    def save(self, *args, **kwargs):
        """Автоматический расчет остатка при сохранении"""
        from decimal import Decimal
        from django.db import transaction
        
        # Проверка на None для balance
        if self.balance is None:
            self.balance = Decimal('0')
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем наличие pk перед обращением к связанным объектам
        # Если объект еще не сохранен (нет pk), устанавливаем значения по умолчанию
        is_new = self.pk is None
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Если total_paid не указан в update_fields,
        # пересчитываем его через агрегацию для предотвращения несогласованности
        update_fields = kwargs.get('update_fields', None)
        if update_fields is None or 'total_paid' not in update_fields:
            if is_new:
                # Для нового объекта платежей еще нет, устанавливаем 0
                self.total_paid = Decimal('0')
            else:
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-3 и BUG-6: Всегда используем блокировку при пересчете
                # Проверка in_atomic_block может не работать корректно, поэтому используем более надежный подход
                # Пересчитываем total_paid через агрегацию с блокировкой для предотвращения race condition
                # Используем select_for_update() всегда, т.к. это безопасно даже вне транзакции
                # (вне транзакции select_for_update() просто не блокирует, но не вызывает ошибок)
                try:
                    # Пытаемся использовать блокировку (работает в транзакции)
                    total_paid = self.payments.select_for_update().aggregate(
                        total=models.Sum('amount')
                    )['total'] or Decimal('0')
                except Exception:
                    # Если select_for_update() не работает (например, вне транзакции в SQLite),
                    # используем обычную агрегацию
                    total_paid = self.payments.aggregate(
                        total=models.Sum('amount')
                    )['total'] or Decimal('0')
                self.total_paid = total_paid
        
        # Преобразуем balance в Decimal для корректного сравнения
        balance_decimal = Decimal(str(self.balance)) if self.balance is not None else Decimal('0')
        self.remaining_amount = balance_decimal - self.total_paid
        
        # Обновление статуса на основе суммы оплаты и типа последнего платежа
        if is_new:
            # Для нового объекта устанавливаем статус по умолчанию
            self.status = 'pending'
        elif self.total_paid == 0:
            self.status = 'pending'
        elif self.total_paid >= balance_decimal:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Если оплата полная или больше баланса, статус должен быть 'paid'
            # Это должно быть приоритетнее проверки типа последнего платежа
            self.status = 'paid'
        else:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем блокировку при запросе last_payment
            # для предотвращения race condition
            try:
                in_atomic = transaction.get_connection().in_atomic_block
            except (AttributeError, Exception):
                # Если не удалось проверить, предполагаем, что мы не в транзакции
                in_atomic = False
            
            if in_atomic:
                last_payment = self.payments.select_for_update().order_by('-created_at').first()
            else:
                last_payment = self.payments.order_by('-created_at').first()
            
            if last_payment:
                if last_payment.payment_type == 'deposit':
                    self.status = 'pending'  # Депозит - ожидает доплаты
                elif last_payment.payment_type == 'final_payment':
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-25: Проверяем, что сумма действительно покрывает остаток
                    # Финальный платеж должен покрывать весь остаток, иначе это частичный платеж
                    if self.total_paid >= balance_decimal:
                        self.status = 'paid'  # Финальный платеж покрыл весь остаток
                    else:
                        self.status = 'partial'  # Финальный платеж, но сумма недостаточна
                else:
                    self.status = 'partial'  # Частичный платеж
            else:
                self.status = 'partial'
            
        # Проверка просрочки (только если статус не 'paid')
        if self.status != 'paid' and self.due_date and timezone.now().date() > self.due_date:
            self.status = 'overdue'
            
        super().save(*args, **kwargs)
    
    @property
    def is_overdue(self):
        """Проверка просрочки платежа"""
        if self.due_date and timezone.now().date() > self.due_date and self.status != 'paid':
            return True
        return False
    
    @property
    def payment_progress_percentage(self):
        """Процент оплаты"""
        from decimal import Decimal
        
        # Преобразуем в Decimal для корректного сравнения
        balance_decimal = Decimal(str(self.balance)) if self.balance is not None else Decimal('0')
        total_paid_decimal = Decimal(str(self.total_paid)) if self.total_paid is not None else Decimal('0')
        
        # Проверка на None и отрицательные значения
        if balance_decimal <= 0:
            return 0
        
        # Если оплачено больше или равно балансу, возвращаем 100%
        if total_paid_decimal >= balance_decimal:
            return 100
        
        # Безопасное деление
        try:
            return float((total_paid_decimal / balance_decimal) * 100)
        except (ZeroDivisionError, TypeError):
            return 0


class InvoicePayment(models.Model):
    """
    Модель для отдельных платежей по инвойсу.
    
    Позволяет отслеживать частичные платежи:
    - Сумма платежа
    - Дата платежа
    - Тип платежа (депозит, финальный платеж)
    - Скриншот чека оплаты
    """
    
    PAYMENT_TYPE_CHOICES = [
        ('deposit', 'Депозит'),
        ('final_payment', 'Финальный платеж'),
        ('partial_payment', 'Частичный платеж'),
        ('refund', 'Возврат'),
    ]
    
    invoice = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        verbose_name="Инвойс",
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        verbose_name="Сумма платежа"
    )
    payment_date = models.DateField(
        verbose_name="Дата платежа"
    )
    payment_type = models.CharField(
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        default='partial_payment',
        verbose_name="Тип платежа"
    )
    payment_receipt = models.FileField(
        upload_to='payments/receipts/',
        validators=[
            FileExtensionValidator(allowed_extensions=['jpg', 'jpeg', 'png', 'pdf']),
        ],
        verbose_name="Скриншот чека оплаты",
        help_text="Фото или скриншот подтверждения оплаты"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Комментарии",
        help_text="Дополнительная информация о платеже"
    )
    
    # Метаданные
    created_by = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        verbose_name="Создал"
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    
    class Meta:
        verbose_name = "Платеж по инвойсу"
        verbose_name_plural = "Платежи по инвойсам"
        ordering = ['-payment_date', '-created_at']
    
    def __str__(self):
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к invoice.invoice_number
        invoice_number = self.invoice.invoice_number if self.invoice else "Без инвойса"
        return f"Платеж {self.amount} от {self.payment_date} по инвойсу {invoice_number}"
    
    def save(self, *args, **kwargs):
        """Обновление общей суммы оплаты инвойса при сохранении платежа"""
        super().save(*args, **kwargs)
        
        # Пересчет общей суммы оплаты
        self._update_invoice_total()
    
    def delete(self, *args, **kwargs):
        """Обновление общей суммы оплаты при удалении платежа"""
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Сохраняем invoice_id до удаления,
        # т.к. после super().delete() объект self будет удален
        invoice_id = self.invoice_id
        
        super().delete(*args, **kwargs)
        
        # Пересчет общей суммы оплаты
        # Используем invoice_id для получения свежего объекта после удаления
        # ВАЖНО: Используем прямой импорт Invoice, т.к. мы уже в модуле models
        try:
            invoice = Invoice.objects.get(pk=invoice_id)
            self._update_invoice_total_for_invoice(invoice)
        except Invoice.DoesNotExist:
            # Если инвойс был удален вместе с заказом, ничего не делаем
            pass
    
    def _update_invoice_total(self):
        """Обновление общей суммы оплаты для текущего инвойса"""
        self._update_invoice_total_for_invoice(self.invoice)
    
    def _update_invoice_total_for_invoice(self, invoice):
        """Обновление общей суммы оплаты для указанного инвойса"""
        from django.db import transaction
        from django.db.models import F
        from decimal import Decimal
        
        # Используем транзакцию и блокировку для предотвращения race condition
        with transaction.atomic():
            # Блокируем инвойс для обновления
            invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
            
            # Пересчитываем сумму через агрегацию
            total_paid = invoice.payments.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')
            
            invoice.total_paid = total_paid
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: НЕ используем update_fields, т.к. это пропускает логику save()
            # Нужно вызвать полный save() чтобы пересчитались remaining_amount и status
            # Это критично для правильного обновления статуса при полной оплате
            # Передаем update_fields=['total_paid'] чтобы избежать двойного пересчета в save(),
            # но это означает, что save() не пересчитает total_paid снова (что правильно, т.к. мы уже пересчитали)
            # Однако, это также означает, что логика пересчета статуса в save() НЕ выполнится!
            # Поэтому НЕ используем update_fields - вызываем полный save()
            invoice.save()


class OrderCBM(models.Model):
    """
    Модель для хранения записей CBM (кубических метров) для заказа.
    
    Позволяет добавлять несколько записей CBM, которые суммируются
    для получения общего объема заказа.
    """
    
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        verbose_name="Заказ",
        related_name='cbm_records'
    )
    cbm_value = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        verbose_name="CBM",
        help_text="Объем в кубических метрах"
    )
    date = models.DateField(
        verbose_name="Дата",
        help_text="Дата добавления CBM"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Комментарии",
        help_text="Дополнительная информация о CBM"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Создал",
        related_name='created_cbm_records'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    
    class Meta:
        verbose_name = "Запись CBM"
        verbose_name_plural = "Записи CBM"
        ordering = ['-date', '-created_at']
    
    def __str__(self):
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасное форматирование с ограничением длины и проверкой на None
        if self.order and self.order.title:
            order_title = self.order.title[:50] + '...' if len(self.order.title) > 50 else self.order.title
        else:
            order_title = "Без заказа"
        return f"CBM {self.cbm_value} для заказа {order_title} ({self.date})"


class Shipment(models.Model):
    """
    Модель для фуры/отправки, которая может содержать несколько заказов.
    
    Используется для отслеживания фактически полученных кубов,
    когда товары от разных фабрик грузятся в одну фуру.
    """
    
    shipment_number = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Номер фуры",
        help_text="Уникальный номер фуры/отправки"
    )
    orders = models.ManyToManyField(
        Order,
        related_name='shipments',
        verbose_name="Заказы",
        help_text="Заказы, которые входят в эту фуру"
    )
    received_cbm = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        null=True,
        blank=True,
        verbose_name="Фактические кубы",
        help_text="Фактически полученные кубы в фуре"
    )
    shipment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата отправки",
        help_text="Дата отправки фуры"
    )
    received_date = models.DateField(
        null=True,
        blank=True,
        verbose_name="Дата получения",
        help_text="Дата получения товара"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Комментарии",
        help_text="Дополнительная информация о фуре"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Создал",
        related_name='created_shipments'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    
    class Meta:
        verbose_name = "Фура"
        verbose_name_plural = "Фуры"
        ordering = ['-shipment_date', '-created_at']
    
    def __str__(self):
        return f"Фура {self.shipment_number}"
    
    @property
    def total_invoice_cbm(self):
        """
        Сумма всех кубов из инвойсов заказов в этой фуре.
        """
        from django.db.models import Sum
        from decimal import Decimal
        
        total = Decimal('0')
        for order in self.orders.all():
            # Суммируем все CBM записи заказа
            order_cbm = order.cbm_records.aggregate(
                total=Sum('cbm_value')
            )['total'] or Decimal('0')
            total += order_cbm
        
        return total
    
    @property
    def cbm_difference(self):
        """
        Разница между заявленными кубами (из инвойсов) и фактическими кубами.
        Положительное значение = фактически меньше, чем заявлено
        Отрицательное значение = фактически больше, чем заявлено
        """
        from decimal import Decimal
        
        if self.received_cbm is None:
            return None
        
        invoice_cbm = self.total_invoice_cbm
        return invoice_cbm - Decimal(str(self.received_cbm))
    
    @property
    def cbm_difference_percentage(self):
        """
        Процент отклонения фактических кубов от заявленных.
        """
        from decimal import Decimal
        
        if self.received_cbm is None or self.total_invoice_cbm == 0:
            return None
        
        difference = self.cbm_difference
        if difference is None:
            return None
        
        percentage = (difference / self.total_invoice_cbm) * 100
        return float(percentage)
    
    @property
    def orders_count(self):
        """Количество заказов в фуре"""
        return self.orders.count()


class EFacturaBasket(models.Model):
    """
    Модель для корзины E-Factura Turkey.
    
    Корзины автоматически создаются по месяцам для организации файлов E-Factura.
    Пример: Январь 2025, Февраль 2026 и т.д.
    """
    
    name = models.CharField(
        max_length=100,
        verbose_name="Название корзины",
        help_text="Например: Январь 2025, Февраль 2026"
    )
    month = models.PositiveIntegerField(
        verbose_name="Месяц",
        help_text="Номер месяца (1-12)"
    )
    year = models.PositiveIntegerField(
        verbose_name="Год",
        help_text="Год (например, 2025)"
    )
    basket_date = models.DateField(
        verbose_name="Дата корзины",
        help_text="Дата, связанная с корзиной"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Создал",
        related_name='created_efactura_baskets'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Дата обновления"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Комментарии",
        help_text="Дополнительная информация о корзине"
    )
    
    class Meta:
        verbose_name = "Корзина E-Factura"
        verbose_name_plural = "Корзины E-Factura"
        ordering = ['-year', '-month', '-created_at']
        unique_together = [['month', 'year']]
    
    def __str__(self):
        return f"E-Factura {self.name}"
    
    @classmethod
    def get_or_create_for_month(cls, year, month, user=None):
        """
        Получить или создать корзину для указанного месяца и года.
        
        Args:
            year: Год (например, 2025)
            month: Месяц (1-12)
            user: Пользователь, создающий корзину
        
        Returns:
            tuple: (EFacturaBasket, created)
        """
        from datetime import date
        from calendar import month_name
        from django.core.exceptions import ValidationError
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Валидация параметров
        if not isinstance(month, int) or month < 1 or month > 12:
            raise ValidationError(f'Месяц должен быть числом от 1 до 12, получено: {month}')
        
        if not isinstance(year, int) or year < 2000 or year > 2100:
            raise ValidationError(f'Год должен быть разумным числом (2000-2100), получено: {year}')
        
        # Получаем название месяца
        month_name_ru = {
            1: 'Январь', 2: 'Февраль', 3: 'Март', 4: 'Апрель',
            5: 'Май', 6: 'Июнь', 7: 'Июль', 8: 'Август',
            9: 'Сентябрь', 10: 'Октябрь', 11: 'Ноябрь', 12: 'Декабрь'
        }
        
        name = f"{month_name_ru.get(month, 'Неизвестно')} {year}"
        basket_date = date(year, month, 1)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем get_or_create с обработкой IntegrityError
        # для предотвращения race condition при одновременном создании корзины
        try:
            basket, created = cls.objects.get_or_create(
                month=month,
                year=year,
                defaults={
                    'name': name,
                    'basket_date': basket_date,
                    'created_by': user
                }
            )
        except Exception as e:
            # Если произошла ошибка (например, IntegrityError из-за race condition),
            # пытаемся получить существующую корзину
            try:
                basket = cls.objects.get(month=month, year=year)
                created = False
            except cls.DoesNotExist:
                # Если корзина не найдена, пробрасываем исходную ошибку
                raise
        
        return basket, created


class EFacturaFile(models.Model):
    """
    Модель для файлов E-Factura в корзинах.
    
    Файлы автоматически распределяются по корзинам на основе даты загрузки.
    """
    
    basket = models.ForeignKey(
        EFacturaBasket,
        on_delete=models.CASCADE,
        verbose_name="Корзина",
        related_name='files'
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        verbose_name="Заказ",
        related_name='efactura_files'
    )
    file = models.FileField(
        upload_to='efactura/files/',
        validators=[
            FileExtensionValidator(allowed_extensions=['pdf', 'xml', 'xlsx', 'xls']),
        ],
        verbose_name="Файл E-Factura"
    )
    upload_date = models.DateField(
        verbose_name="Дата загрузки",
        help_text="Дата загрузки файла"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Загрузил",
        related_name='uploaded_efactura_files'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата создания"
    )
    notes = models.TextField(
        blank=True,
        verbose_name="Комментарии",
        help_text="Дополнительная информация о файле"
    )
    
    class Meta:
        verbose_name = "Файл E-Factura"
        verbose_name_plural = "Файлы E-Factura"
        ordering = ['-upload_date', '-created_at']
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-8: Уникальное ограничение для предотвращения дубликатов
        unique_together = [['order', 'basket']]
    
    def __str__(self):
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к order.title
        order_title = self.order.title if self.order else "Без заказа"
        return f"E-Factura файл для заказа {order_title} ({self.upload_date})"
    
    def delete(self, *args, **kwargs):
        """
        Удаление файла E-Factura с удалением физического файла из файловой системы.
        """
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Сохраняем путь к файлу до удаления модели
        file_path = None
        if self.file:
            file_path = self.file.path if hasattr(self.file, 'path') else None
        
        # Удаляем модель (это также удалит файл через Django)
        super().delete(*args, **kwargs)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Явно удаляем файл из файловой системы, если он существует
        if file_path:
            import os
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                import logging
                logger = logging.getLogger('orders')
                logger.warning(f"Не удалось удалить файл E-Factura {file_path}: {e}")
    
    def save(self, *args, **kwargs):
        """
        Автоматическое распределение файла по корзине на основе даты загрузки.
        """
        from datetime import date
        
        # Если дата загрузки не указана, используем текущую дату
        if not self.upload_date:
            self.upload_date = date.today()
        
        # Если корзина не указана, создаем или получаем корзину для месяца загрузки
        if not self.basket_id:
            year = self.upload_date.year
            month = self.upload_date.month
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Если created_by не указан, передаем None
            basket, _ = EFacturaBasket.get_or_create_for_month(
                year=year,
                month=month,
                user=self.created_by if self.created_by else None
            )
            self.basket = basket
        else:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем соответствие корзины дате загрузки
            # Если корзина указана, но не соответствует дате, предупреждаем (но не блокируем)
            if self.basket and self.upload_date:
                if self.basket.year != self.upload_date.year or self.basket.month != self.upload_date.month:
                    # Логируем предупреждение, но не блокируем сохранение
                    import logging
                    logger = logging.getLogger('orders')
                    logger.warning(
                        f'Файл E-Factura загружается в корзину {self.basket.name}, '
                        f'но дата загрузки ({self.upload_date}) не соответствует месяцу корзины '
                        f'({self.basket.month}/{self.basket.year})'
                    )
        
        super().save(*args, **kwargs)
