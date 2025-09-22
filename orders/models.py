from typing import Optional, Dict, Any, List
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import FileExtensionValidator
from django.template.loader import render_to_string
from django.conf import settings
from .validators import validate_excel_file, validate_pdf_file, validate_safe_filename


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
        return f"{self.name} ({self.country.name})"


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
    
    class Meta:
        verbose_name = "Заказ"
        verbose_name_plural = "Заказы"
        ordering = ['-uploaded_at']
    
    def __str__(self):
        return f"{self.title} - {self.factory.name}"
    
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
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save()
    
    def mark_invoice_received(self, invoice_file):
        """Отметить получение инвойса"""
        self.status = 'invoice_received'
        self.invoice_file = invoice_file
        self.invoice_received_at = timezone.now()
        self.save()
    
    def mark_as_completed(self):
        """Отметить заказ как завершенный"""
        self.status = 'completed'
        self.completed_at = timezone.now()
        self.save()
    
    def clean(self) -> None:
        """Валидация модели"""
        super().clean()

        # Валидация имени файла
        if self.excel_file:
            validate_safe_filename(self.excel_file.name)
        if self.invoice_file:
            validate_safe_filename(self.invoice_file.name)
    
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
        verbose_name="Напоминания о неотправленных заказах"
    )
    notify_sent_reminder = models.BooleanField(
        default=True, 
        verbose_name="Напоминания о заказах без инвойса"
    )
    notify_invoice_received = models.BooleanField(
        default=True, 
        verbose_name="Уведомления о получении инвойса"
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
    expires_at = models.DateTimeField(verbose_name="Истекает")
    
    class Meta:
        verbose_name = "Подтверждение операции"
        verbose_name_plural = "Подтверждения операций"
        ordering = ['-requested_at']
    
    def __str__(self):
        return f"{self.get_action_display()} для заказа {self.order.title}"
    
    def save(self, *args, **kwargs):
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(hours=24)
        super().save(*args, **kwargs)
    
    def is_expired(self):
        """Проверка истечения срока подтверждения"""
        return timezone.now() > self.expires_at
    
    def can_be_confirmed_by(self, user):
        """Проверка, может ли пользователь подтвердить операцию"""
        # Пока что только создатель заказа может подтвердить
        # В будущем можно добавить роли и права
        return self.order.employee == user
    
    def confirm(self, user, comments=""):
        """Подтверждение операции"""
        if not self.can_be_confirmed_by(user):
            raise ValueError("Пользователь не может подтвердить эту операцию")
        
        self.status = 'confirmed'
        self.confirmed_by = user
        self.confirmed_at = timezone.now()
        self.comments = comments
        self.save()
    
    def reject(self, user, reason=""):
        """Отклонение операции"""
        if not self.can_be_confirmed_by(user):
            raise ValueError("Пользователь не может отклонить эту операцию")
        
        self.status = 'rejected'
        self.confirmed_by = user
        self.confirmed_at = timezone.now()
        self.rejection_reason = reason
        self.save()


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
        return f"{self.get_action_display()} заказа {self.order.title} пользователем {self.user.username}"
    
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
