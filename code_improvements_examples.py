#!/usr/bin/env python3
"""
Примеры улучшений кода для соответствия принципам KISS, SOLID, DRY
"""

# ============================================================================
# 1. УСТРАНЕНИЕ ДУБЛИРОВАНИЯ КОДА (DRY)
# ============================================================================

# ❌ ПЛОХО: Дублирование логики проверки авторизации
def bad_example_1():
    """Пример дублирования кода"""
    # В каждом view повторяется:
    if not request.user.is_authenticated:
        return redirect('login')
    
    if not request.user.has_perm('orders.view_order'):
        messages.error(request, 'У вас нет прав для просмотра заказов')
        return redirect('home')

# ✅ ХОРОШО: Создание декоратора для устранения дублирования
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

def require_permission(permission_name):
    """Декоратор для проверки прав доступа"""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('login')
            
            if not request.user.has_perm(permission_name):
                messages.error(request, f'У вас нет прав для выполнения этого действия')
                return redirect('home')
            
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

# Использование:
@require_permission('orders.view_order')
def order_list(request):
    # Логика view
    pass

# ============================================================================
# 2. УПРОЩЕНИЕ СЛОЖНЫХ ФУНКЦИЙ (KISS)
# ============================================================================

# ❌ ПЛОХО: Сложная функция с множественной ответственностью
def bad_complex_function(order_id, notification_type):
    """Сложная функция с цикломатической сложностью >10"""
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
        
        # Получаем шаблон уведомления
        try:
            template = NotificationTemplate.objects.get(template_type=notification_type)
        except NotificationTemplate.DoesNotExist:
            return f"Шаблон для типа {notification_type} не найден"
        
        # Создаем уведомление
        if notification_type == 'order_uploaded':
            title = f"Новый заказ: {order.title}"
            message = f"Заказ '{order.title}' для фабрики '{order.factory.name}' был загружен"
        elif notification_type == 'order_sent':
            title = f"Заказ отправлен: {order.title}"
            message = f"Заказ '{order.title}' отправлен на фабрику '{order.factory.name}'"
        elif notification_type == 'invoice_received':
            title = f"Инвойс получен: {order.title}"
            message = f"Инвойс для заказа '{order.title}' получен от фабрики '{order.factory.name}'"
        else:
            return f"Неизвестный тип уведомления: {notification_type}"
        
        notification = Notification.objects.create(
            user=user,
            order=order,
            notification_type=notification_type,
            title=title,
            message=message
        )
        
        # Отправляем email
        if settings_obj.email_notifications:
            send_notification_email.delay(notification.id)
        
        return f"Уведомление отправлено пользователю {user.username} для заказа {order.title}"
        
    except Order.DoesNotExist:
        return f"Заказ с ID {order_id} не найден"
    except Exception as e:
        return f"Ошибка при отправке уведомления: {str(e)}"

# ✅ ХОРОШО: Разбиение на простые функции
class NotificationService:
    """Сервис для работы с уведомлениями"""
    
    def __init__(self, order_id: int, notification_type: str):
        self.order_id = order_id
        self.notification_type = notification_type
        self.order = None
        self.user = None
        self.settings = None
    
    def _get_order(self) -> bool:
        """Получение заказа"""
        try:
            self.order = Order.objects.get(id=self.order_id)
            self.user = self.order.employee
            return True
        except Order.DoesNotExist:
            return False
    
    def _get_user_settings(self) -> bool:
        """Получение настроек пользователя"""
        try:
            self.settings = NotificationSettings.objects.get(user=self.user)
            return True
        except NotificationSettings.DoesNotExist:
            self.settings = NotificationSettings.objects.create(user=self.user)
            return True
    
    def _create_notification(self) -> Notification:
        """Создание уведомления"""
        title, message = self._get_notification_content()
        
        return Notification.objects.create(
            user=self.user,
            order=self.order,
            notification_type=self.notification_type,
            title=title,
            message=message
        )
    
    def _get_notification_content(self) -> tuple:
        """Получение содержимого уведомления"""
        content_map = {
            'order_uploaded': (
                f"Новый заказ: {self.order.title}",
                f"Заказ '{self.order.title}' для фабрики '{self.order.factory.name}' был загружен"
            ),
            'order_sent': (
                f"Заказ отправлен: {self.order.title}",
                f"Заказ '{self.order.title}' отправлен на фабрику '{self.order.factory.name}'"
            ),
            'invoice_received': (
                f"Инвойс получен: {self.order.title}",
                f"Инвойс для заказа '{self.order.title}' получен от фабрики '{self.order.factory.name}'"
            )
        }
        
        return content_map.get(self.notification_type, ("Уведомление", "Новое уведомление"))
    
    def send_notification(self) -> str:
        """Основной метод отправки уведомления"""
        if not self._get_order():
            return f"Заказ с ID {self.order_id} не найден"
        
        if not self._get_user_settings():
            return f"Ошибка при получении настроек пользователя"
        
        if not self.settings.email_notifications:
            return f"Email уведомления отключены для пользователя {self.user.username}"
        
        notification = self._create_notification()
        
        if self.settings.email_notifications:
            send_notification_email.delay(notification.id)
        
        return f"Уведомление отправлено пользователю {self.user.username} для заказа {self.order.title}"

# ============================================================================
# 3. СОЗДАНИЕ КОНСТАНТ (Clean Code)
# ============================================================================

# ❌ ПЛОХО: Магические числа
def bad_constants_example():
    """Пример использования магических чисел"""
    # orders/models.py
    title = models.CharField(max_length=200)  # Магическое число
    paginate_by = 20  # Магическое число
    max_file_size = 10 * 1024 * 1024  # Магическое число

# ✅ ХОРОШО: Использование констант
# constants.py
class ModelConstants:
    """Константы для моделей"""
    MAX_TITLE_LENGTH = 200
    MAX_DESCRIPTION_LENGTH = 1000
    MAX_COMMENT_LENGTH = 500
    MAX_PHONE_LENGTH = 20
    MAX_DEPARTMENT_LENGTH = 100
    MAX_POSITION_LENGTH = 100

class ViewConstants:
    """Константы для views"""
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    SEARCH_MIN_LENGTH = 2
    SEARCH_MAX_LENGTH = 100

class FileConstants:
    """Константы для файлов"""
    MAX_EXCEL_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_PDF_SIZE = 5 * 1024 * 1024     # 5MB
    ALLOWED_EXCEL_EXTENSIONS = ['xlsx', 'xls']
    ALLOWED_PDF_EXTENSIONS = ['pdf']

class NotificationConstants:
    """Константы для уведомлений"""
    DEFAULT_REMINDER_FREQUENCY = 7  # дней
    MAX_TITLE_LENGTH = 200
    MAX_MESSAGE_LENGTH = 1000
    EXPIRATION_HOURS = 24

# Использование:
from .constants import ModelConstants

class Order(models.Model):
    title = models.CharField(max_length=ModelConstants.MAX_TITLE_LENGTH)

# ============================================================================
# 4. СОЗДАНИЕ БАЗОВЫХ КЛАССОВ (DRY + SOLID)
# ============================================================================

# ✅ ХОРОШО: Базовый класс для общих полей
class TimestampedModel(models.Model):
    """Базовый класс с полями времени"""
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    
    class Meta:
        abstract = True

class UserOwnedModel(models.Model):
    """Базовый класс для моделей, принадлежащих пользователю"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Пользователь")
    
    class Meta:
        abstract = True

# Использование:
class Order(TimestampedModel, UserOwnedModel):
    title = models.CharField(max_length=ModelConstants.MAX_TITLE_LENGTH)
    # created_at, updated_at, user автоматически добавлены

# ✅ ХОРОШО: Базовый класс для views
class BaseOrderView:
    """Базовый класс для views заказов"""
    
    def get_queryset(self):
        """Получение queryset для текущего пользователя"""
        return Order.objects.filter(employee=self.request.user)
    
    def get_context_data(self, **kwargs):
        """Добавление общих данных в контекст"""
        context = super().get_context_data(**kwargs)
        context['user_orders_count'] = self.get_queryset().count()
        return context

# ============================================================================
# 5. СОЗДАНИЕ УТИЛИТ (DRY)
# ============================================================================

# ✅ ХОРОШО: Утилиты для общих операций
class FileUtils:
    """Утилиты для работы с файлами"""
    
    @staticmethod
    def get_file_size_mb(file) -> float:
        """Получение размера файла в MB"""
        return file.size / (1024 * 1024)
    
    @staticmethod
    def is_valid_file_type(file, allowed_extensions: list) -> bool:
        """Проверка типа файла"""
        extension = file.name.split('.')[-1].lower()
        return extension in allowed_extensions
    
    @staticmethod
    def generate_unique_filename(original_filename: str) -> str:
        """Генерация уникального имени файла"""
        import uuid
        extension = original_filename.split('.')[-1]
        return f"{uuid.uuid4()}.{extension}"

class DateUtils:
    """Утилиты для работы с датами"""
    
    @staticmethod
    def days_between(date1, date2) -> int:
        """Количество дней между датами"""
        return (date2 - date1).days
    
    @staticmethod
    def is_overdue(date, days_threshold: int) -> bool:
        """Проверка просрочки"""
        from django.utils import timezone
        return DateUtils.days_between(date, timezone.now()) > days_threshold

# ============================================================================
# 6. СОЗДАНИЕ МИКСИНОВ (SOLID)
# ============================================================================

# ✅ ХОРОШО: Миксины для общих функций
class PermissionRequiredMixin:
    """Миксин для проверки прав доступа"""
    permission_required = None
    
    def dispatch(self, request, *args, **kwargs):
        if not request.user.has_perm(self.permission_required):
            messages.error(request, 'У вас нет прав для выполнения этого действия')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)

class UserOwnedMixin:
    """Миксин для объектов, принадлежащих пользователю"""
    
    def get_queryset(self):
        """Фильтрация по пользователю"""
        return super().get_queryset().filter(employee=self.request.user)

class PaginationMixin:
    """Миксин для пагинации"""
    paginate_by = ViewConstants.DEFAULT_PAGE_SIZE
    
    def get_paginate_by(self, queryset):
        """Получение размера страницы"""
        return self.request.GET.get('page_size', self.paginate_by)

# Использование:
class OrderListView(PermissionRequiredMixin, UserOwnedMixin, PaginationMixin, ListView):
    permission_required = 'orders.view_order'
    model = Order
    template_name = 'orders/order_list.html'

# ============================================================================
# 7. СОЗДАНИЕ СЕРВИСОВ (SOLID)
# ============================================================================

# ✅ ХОРОШО: Сервисы для бизнес-логики
class OrderService:
    """Сервис для работы с заказами"""
    
    def __init__(self, order: Order):
        self.order = order
    
    def can_be_sent(self) -> bool:
        """Проверка возможности отправки заказа"""
        return self.order.status == 'uploaded' and self.order.excel_file
    
    def can_be_completed(self) -> bool:
        """Проверка возможности завершения заказа"""
        return self.order.status == 'invoice_received' and self.order.invoice_file
    
    def get_next_status(self) -> str:
        """Получение следующего статуса"""
        status_flow = {
            'uploaded': 'sent',
            'sent': 'invoice_received',
            'invoice_received': 'completed'
        }
        return status_flow.get(self.order.status)

class EmailService:
    """Сервис для отправки email"""
    
    @staticmethod
    def send_notification(notification: Notification) -> bool:
        """Отправка уведомления"""
        try:
            # Логика отправки email
            return True
        except Exception as e:
            logger.error(f"Ошибка отправки email: {e}")
            return False

# ============================================================================
# 8. СОЗДАНИЕ ВАЛИДАТОРОВ (SOLID)
# ============================================================================

# ✅ ХОРОШО: Специализированные валидаторы
class OrderValidator:
    """Валидатор для заказов"""
    
    @staticmethod
    def validate_title(title: str) -> bool:
        """Валидация названия заказа"""
        return len(title.strip()) >= 3 and len(title) <= ModelConstants.MAX_TITLE_LENGTH
    
    @staticmethod
    def validate_factory(factory: Factory) -> bool:
        """Валидация фабрики"""
        return factory.is_active and factory.email

class FileValidator:
    """Валидатор для файлов"""
    
    @staticmethod
    def validate_excel_file(file) -> bool:
        """Валидация Excel файла"""
        if not FileUtils.is_valid_file_type(file, FileConstants.ALLOWED_EXCEL_EXTENSIONS):
            return False
        
        if FileUtils.get_file_size_mb(file) > FileConstants.MAX_EXCEL_SIZE / (1024 * 1024):
            return False
        
        return True

# ============================================================================
# ЗАКЛЮЧЕНИЕ
# ============================================================================

"""
Эти примеры показывают, как можно улучшить код для соответствия принципам:

1. DRY: Устранение дублирования через декораторы, миксины, утилиты
2. KISS: Разбиение сложных функций на простые
3. SOLID: Создание специализированных классов и сервисов
4. Clean Code: Использование констант вместо магических чисел
5. YAGNI: Простые и понятные решения

Применение этих принципов сделает код более:
- Читаемым
- Поддерживаемым
- Тестируемым
- Расширяемым
- Надежным
"""
