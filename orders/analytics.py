from django.db.models import Count, Q, Avg
from django.utils import timezone
from datetime import timedelta, datetime
from .models import Order, Factory, Country, Notification
from .constants import TimeConstants


class AnalyticsService:
    """Сервис для аналитики заказов"""
    
    def __init__(self, user=None, date_from=None, date_to=None):
        self.user = user
        self.date_from = date_from or timezone.now() - timedelta(days=TimeConstants.METRICS_RETENTION_DAYS)
        self.date_to = date_to or timezone.now()
        
        # Конвертируем в date объекты если нужно
        if hasattr(self.date_from, 'date'):
            self.date_from = self.date_from.date()
        if hasattr(self.date_to, 'date'):
            self.date_to = self.date_to.date()
        
        # Базовый queryset заказов
        self.orders_queryset = Order.objects.filter(
            uploaded_at__date__range=[self.date_from, self.date_to]
        )
        
        if self.user:
            self.orders_queryset = self.orders_queryset.filter(employee=self.user)
    
    def get_orders_overview(self):
        """Общая статистика по заказам"""
        total_orders = self.orders_queryset.count()
        
        status_stats = self.orders_queryset.values('status').annotate(
            count=Count('id')
        ).order_by('status')
        
        # Конвертируем в словарь для удобства
        status_dict = {item['status']: item['count'] for item in status_stats}
        
        return {
            'total_orders': total_orders,
            'uploaded': status_dict.get('uploaded', 0),
            'sent': status_dict.get('sent', 0),
            'invoice_received': status_dict.get('invoice_received', 0),
            'completed': status_dict.get('completed', 0),
            'cancelled': status_dict.get('cancelled', 0),
        }
    
    def get_factory_stats(self):
        """Статистика по фабрикам"""
        factory_stats = self.orders_queryset.values(
            'factory__name', 
            'factory__country__name'
        ).annotate(
            total_orders=Count('id'),
            uploaded_orders=Count('id', filter=Q(status='uploaded')),
            sent_orders=Count('id', filter=Q(status='sent')),
            completed_orders=Count('id', filter=Q(status='completed')),
        ).order_by('-total_orders')
        
        return list(factory_stats)
    
    def get_country_stats(self):
        """Статистика по странам"""
        country_stats = self.orders_queryset.values(
            'factory__country__name'
        ).annotate(
            total_orders=Count('id'),
            total_factories=Count('factory', distinct=True),
        ).order_by('-total_orders')
        
        return list(country_stats)
    
    def get_employee_stats(self):
        """Статистика по сотрудникам"""
        if not self.user:  # Только для админов
            employee_stats = self.orders_queryset.values(
                'employee__username',
                'employee__first_name',
                'employee__last_name'
            ).annotate(
                total_orders=Count('id'),
                completed_orders=Count('id', filter=Q(status='completed')),
            ).order_by('-total_orders')
            
            # Добавляем процент завершенных заказов
            for stat in employee_stats:
                if stat['total_orders'] > 0:
                    stat['completion_rate'] = round(
                        (stat['completed_orders'] / stat['total_orders']) * 100, 1
                    )
                else:
                    stat['completion_rate'] = 0
            
            return list(employee_stats)
        return []
    
    def get_time_series_data(self, period='day'):
        """Данные для временных рядов"""
        
        # Используем SQLite-совместимые функции
        if period == 'day':
            date_trunc_sql = "DATE(uploaded_at)"
        elif period == 'week':
            date_trunc_sql = "DATE(uploaded_at, 'weekday 0', '-6 days')"  # Начало недели
        elif period == 'month':
            date_trunc_sql = "DATE(uploaded_at, 'start of month')"
        else:
            date_trunc_sql = "DATE(uploaded_at)"
        
        # Группируем по датам используя SQLite-совместимый синтаксис
        time_series = self.orders_queryset.extra(
            select={'period': date_trunc_sql}
        ).values('period').annotate(
            total_orders=Count('id'),
            uploaded_orders=Count('id', filter=Q(status='uploaded')),
            sent_orders=Count('id', filter=Q(status='sent')),
            completed_orders=Count('id', filter=Q(status='completed')),
        ).order_by('period')
        
        return list(time_series)
    
    def get_overdue_orders(self):
        """Просроченные заказы"""
        now = timezone.now()
        overdue_orders = self.orders_queryset.filter(
            Q(
                status='uploaded',
                uploaded_at__lte=now - timedelta(days=TimeConstants.LOG_RETENTION_DAYS)
            ) | Q(
                status='sent',
                sent_at__lte=now - timedelta(days=TimeConstants.LOG_RETENTION_DAYS)
            )
        ).select_related('factory', 'employee')
        
        return list(overdue_orders)
    
    def get_average_processing_time(self):
        """Среднее время обработки заказов"""
        from django.db.models import F, ExpressionWrapper, DurationField
        
        completed_orders = self.orders_queryset.filter(
            status='completed',
            completed_at__isnull=False,
            uploaded_at__isnull=False
        ).annotate(
            processing_time=ExpressionWrapper(
                F('completed_at') - F('uploaded_at'),
                output_field=DurationField()
            )
        ).filter(
            processing_time__gt=timedelta(0)  # completed_at > uploaded_at
        )
        
        if not completed_orders.exists():
            return 0
        
        # Используем агрегацию для вычисления среднего
        from django.db.models import Avg
        avg_duration = completed_orders.aggregate(
            avg_processing=Avg('processing_time')
        )['avg_processing']
        
        if avg_duration:
            return round(avg_duration.total_seconds() / (24 * 3600), 1)  # Конвертируем в дни
        
        return 0
    
    def get_notification_stats(self):
        """Статистика уведомлений"""
        if not self.user:
            return {}
        
        notifications = Notification.objects.filter(
            user=self.user,
            created_at__date__range=[self.date_from, self.date_to]
        )
        
        notification_stats = notifications.values('notification_type').annotate(
            count=Count('id')
        ).order_by('notification_type')
        
        return {item['notification_type']: item['count'] for item in notification_stats}
    
    def get_kpi_metrics(self):
        """Ключевые показатели эффективности"""
        overview = self.get_orders_overview()
        
        # Процент завершенных заказов
        completion_rate = 0
        if overview['total_orders'] > 0:
            completion_rate = round(
                (overview['completed'] / overview['total_orders']) * 100, 1
            )
        
        # Процент заказов с инвойсами
        invoice_rate = 0
        if overview['total_orders'] > 0:
            invoice_rate = round(
                ((overview['invoice_received'] + overview['completed']) / overview['total_orders']) * 100, 1
            )
        
        # Среднее время обработки
        avg_processing_time = self.get_average_processing_time()
        
        # Количество просроченных заказов
        overdue_count = len(self.get_overdue_orders())
        
        return {
            'completion_rate': completion_rate,
            'invoice_rate': invoice_rate,
            'avg_processing_time': avg_processing_time,
            'overdue_count': overdue_count,
            'total_orders': overview['total_orders'],
        }


def get_analytics_data(user=None, date_from=None, date_to=None):
    """Получить все данные аналитики"""
    analytics = AnalyticsService(user, date_from, date_to)
    
    return {
        'overview': analytics.get_orders_overview(),
        'factory_stats': analytics.get_factory_stats(),
        'country_stats': analytics.get_country_stats(),
        'employee_stats': analytics.get_employee_stats(),
        'time_series': analytics.get_time_series_data(),
        'overdue_orders': analytics.get_overdue_orders(),
        'kpi_metrics': analytics.get_kpi_metrics(),
        'notification_stats': analytics.get_notification_stats(),
        'date_range': {
            'from': analytics.date_from.strftime('%Y-%m-%d'),
            'to': analytics.date_to.strftime('%Y-%m-%d'),
        }
    }
