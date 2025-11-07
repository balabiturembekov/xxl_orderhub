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
        return f"{self.get_action_display()} для заказа {self.order.title}"
    
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
        # Пока что только создатель заказа может подтвердить
        # В будущем можно добавить роли и права
        return self.order.employee == user
    
    def confirm(self, user, comments=""):
        """Подтверждение операции"""
        if not self.can_be_confirmed_by(user):
            raise ValueError("Пользователь не может подтвердить эту операцию")
        
        # Атомарное обновление для предотвращения race condition
        updated = OrderConfirmation.objects.filter(
            id=self.id,
            status='pending'
        ).update(
            status='confirmed',
            confirmed_by=user,
            confirmed_at=timezone.now(),
            comments=comments
        )
        
        if updated == 0:
            raise ValueError("Подтверждение уже обработано или истекло")
        
        # Обновляем локальный объект
        self.refresh_from_db()
    
    def reject(self, user, reason=""):
        """Отклонение операции"""
        if not self.can_be_confirmed_by(user):
            raise ValueError("Пользователь не может отклонить эту операцию")
        
        # Атомарное обновление для предотвращения race condition
        updated = OrderConfirmation.objects.filter(
            id=self.id,
            status='pending'
        ).update(
            status='rejected',
            confirmed_by=user,
            confirmed_at=timezone.now(),
            rejection_reason=reason
        )
        
        if updated == 0:
            raise ValueError("Подтверждение уже обработано или истекло")
        
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
        return f"Версия {self.version_number} шаблона {self.template.name}"


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
    
    class Meta:
        verbose_name = "Инвойс"
        verbose_name_plural = "Инвойсы"
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Инвойс {self.invoice_number} для заказа {self.order.title}"
    
    def save(self, *args, **kwargs):
        """Автоматический расчет остатка при сохранении"""
        from decimal import Decimal
        
        # Проверка на None для balance
        if self.balance is None:
            self.balance = Decimal('0')
        
        self.remaining_amount = Decimal(str(self.balance)) - self.total_paid
        
        # Обновление статуса на основе типа последнего платежа
        if self.total_paid == 0:
            self.status = 'pending'
        elif self.total_paid >= Decimal(str(self.balance)):
            self.status = 'paid'
        else:
            # Определяем статус на основе типа последнего платежа
            last_payment = self.payments.order_by('-created_at').first()
            if last_payment:
                if last_payment.payment_type == 'deposit':
                    self.status = 'pending'  # Депозит - ожидает доплаты
                elif last_payment.payment_type == 'final_payment':
                    self.status = 'paid'  # Финальный платеж - полностью оплачен
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
        
        # Проверка на None и отрицательные значения
        if not self.balance or self.balance <= 0:
            return 0
        
        # Если оплачено больше или равно балансу, возвращаем 100%
        if self.total_paid >= self.balance:
            return 100
        
        # Безопасное деление
        try:
            return float((self.total_paid / self.balance) * 100)
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
        return f"Платеж {self.amount} от {self.payment_date} по инвойсу {self.invoice.invoice_number}"
    
    def save(self, *args, **kwargs):
        """Обновление общей суммы оплаты инвойса при сохранении платежа"""
        super().save(*args, **kwargs)
        
        # Пересчет общей суммы оплаты
        self._update_invoice_total()
    
    def delete(self, *args, **kwargs):
        """Обновление общей суммы оплаты при удалении платежа"""
        invoice = self.invoice
        super().delete(*args, **kwargs)
        
        # Пересчет общей суммы оплаты
        self._update_invoice_total_for_invoice(invoice)
    
    def _update_invoice_total(self):
        """Обновление общей суммы оплаты для текущего инвойса"""
        self._update_invoice_total_for_invoice(self.invoice)
    
    def _update_invoice_total_for_invoice(self, invoice):
        """Обновление общей суммы оплаты для указанного инвойса"""
        from django.db import transaction
        from django.db.models import F
        
        # Используем транзакцию и блокировку для предотвращения race condition
        with transaction.atomic():
            # Блокируем инвойс для обновления
            invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
            
            # Пересчитываем сумму через агрегацию
            total_paid = invoice.payments.aggregate(
                total=models.Sum('amount')
            )['total'] or 0
            
            invoice.total_paid = total_paid
            invoice.save(update_fields=['total_paid', 'remaining_amount', 'status'])
