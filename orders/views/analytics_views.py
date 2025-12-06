"""
Analytics and reporting views.

This module handles all analytics-related functionality:
- Analytics dashboard
- Data export functionality
- API endpoints for charts and graphs
- Performance metrics
"""

from typing import Dict, Any
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import TemplateView
from django.http import JsonResponse, HttpResponse
from django.core.cache import cache
import csv

from ..models import Order, Factory, Country, OrderCBM
from ..analytics import get_analytics_data
from django.db.models import Sum, Count, Q
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal


@method_decorator(login_required, name='dispatch')
class AnalyticsDashboardView(TemplateView):
    """
    Display analytics dashboard with key metrics and charts.
    
    Features:
    - Order statistics by status
    - Factory performance metrics
    - Country distribution
    - Time-based trends
    - Export functionality
    """
    template_name = 'orders/analytics_dashboard.html'
    
    def get_context_data(self, **kwargs):
        """Add analytics data to context."""
        context = super().get_context_data(**kwargs)
        
        if self.request.user.is_authenticated:
            # Get analytics data for the authenticated user
            analytics_data = get_analytics_data(self.request.user)
            context.update(analytics_data)
        else:
            # For unauthenticated users, show public statistics
            context.update(self._get_public_statistics())
        
        return context
    
    def _get_public_statistics(self) -> Dict[str, Any]:
        """
        Get public statistics for unauthenticated users.
        
        Returns:
            Dictionary with public statistics
        """
        # Cache public statistics for 10 minutes
        from django.core.cache import cache
        cache_key = "public_statistics"
        cached_stats = cache.get(cache_key)
        
        if cached_stats is None:
            cached_stats = {
                'total_orders': Order.objects.filter(~Q(cancelled_by_client=True)).count(),
                'total_factories': Factory.objects.count(),
                'total_countries': Country.objects.count(),
                'active_users': Order.objects.filter(~Q(cancelled_by_client=True)).values('employee').distinct().count(),
            }
            cache.set(cache_key, cached_stats, 600)  # 10 minutes
        
        return cached_stats


@login_required
def analytics_export(request):
    """
    Export analytics data to CSV format.
    
    Returns:
        HttpResponse with CSV file containing analytics data
    """
    # Get analytics data
    analytics_data = get_analytics_data(request.user)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics_export.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow(['Metric', 'Value'])
    
    # Write data
    writer.writerow(['Total Orders', analytics_data.get('total_orders', 0)])
    writer.writerow(['Orders by Status'])
    
    for status, count in analytics_data.get('orders_by_status', {}).items():
        writer.writerow([f'  {status}', count])
    
    writer.writerow(['Orders by Factory'])
    for factory_name, count in analytics_data.get('orders_by_factory', {}).items():
        writer.writerow([f'  {factory_name}', count])
    
    writer.writerow(['Orders by Country'])
    for country_name, count in analytics_data.get('orders_by_country', {}).items():
        writer.writerow([f'  {country_name}', count])
    
    return response


@login_required
def analytics_api(request):
    """
    API endpoint for analytics data in JSON format.
    
    Used by JavaScript charts and graphs on the frontend.
    
    Returns:
        JsonResponse with analytics data
    """
    analytics_data = get_analytics_data(request.user)
    
    # Format data for charts
    chart_data = {
        'orders_by_status': {
            'labels': list(analytics_data.get('orders_by_status', {}).keys()),
            'data': list(analytics_data.get('orders_by_status', {}).values())
        },
        'orders_by_factory': {
            'labels': list(analytics_data.get('orders_by_factory', {}).keys())[:10],  # Top 10
            'data': list(analytics_data.get('orders_by_factory', {}).values())[:10]
        },
        'orders_by_country': {
            'labels': list(analytics_data.get('orders_by_country', {}).keys()),
            'data': list(analytics_data.get('orders_by_country', {}).values())
        },
        'monthly_trends': analytics_data.get('monthly_trends', {}),
        'performance_metrics': analytics_data.get('performance_metrics', {})
    }
    
    return JsonResponse(chart_data)


@method_decorator(login_required, name='dispatch')
class CBMAnalyticsView(TemplateView):
    """
    Аналитика CBM (кубических метров) по странам.
    
    Отображает:
    - Общее количество CBM по странам
    - Количество заказов с CBM по странам
    - Детальную статистику по каждой стране
    - Фильтры по датам
    """
    template_name = 'orders/cbm_analytics.html'
    
    def get_context_data(self, **kwargs):
        """Добавляем данные аналитики CBM по странам."""
        context = super().get_context_data(**kwargs)
        
        # Получаем параметры фильтрации
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        # Устанавливаем диапазон дат
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            except (ValueError, AttributeError):
                date_from = None
        else:
            # По умолчанию - последние 90 дней
            date_from = timezone.now().date() - timedelta(days=90)
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            except (ValueError, AttributeError):
                date_to = None
        else:
            date_to = timezone.now().date()
        
        # Базовый queryset для CBM записей
        cbm_queryset = OrderCBM.objects.select_related(
            'order', 
            'order__factory', 
            'order__factory__country'
        )
        
        # Фильтрация по дате создания CBM записи
        if date_from:
            cbm_queryset = cbm_queryset.filter(date__gte=date_from)
        if date_to:
            cbm_queryset = cbm_queryset.filter(date__lte=date_to)
        
        # Фильтрация по пользователю (если нужно)
        if self.request.user and not self.request.user.is_superuser:
            cbm_queryset = cbm_queryset.filter(order__employee=self.request.user)
        
        # Группируем по странам и считаем сумму CBM
        country_cbm_stats = cbm_queryset.values(
            'order__factory__country__code',
            'order__factory__country__name'
        ).annotate(
            total_cbm=Sum('cbm_value'),
            total_orders=Count('order', distinct=True),
            total_records=Count('id')
        ).order_by('-total_cbm')
        
        # Конвертируем в список для удобства работы в шаблоне
        country_stats = []
        total_cbm_all = Decimal('0')
        
        for stat in country_cbm_stats:
            total_cbm = stat['total_cbm'] or Decimal('0')
            total_cbm_all += total_cbm
            
            country_stats.append({
                'country_code': stat['order__factory__country__code'],
                'country_name': stat['order__factory__country__name'],
                'total_cbm': total_cbm,
                'total_orders': stat['total_orders'],
                'total_records': stat['total_records'],
            })
        
        # Дополнительная статистика
        total_orders_with_cbm = cbm_queryset.values('order').distinct().count()
        total_cbm_records = cbm_queryset.count()
        
        # Средний CBM на заказ по странам и процент от общего
        for stat in country_stats:
            if stat['total_orders'] > 0:
                stat['avg_cbm_per_order'] = round(
                    float(stat['total_cbm'] / stat['total_orders']), 3
                )
            else:
                stat['avg_cbm_per_order'] = 0
            
            # Вычисляем процент от общего CBM
            if total_cbm_all > 0:
                stat['percentage'] = round(
                    float((stat['total_cbm'] / total_cbm_all) * 100), 1
                )
            else:
                stat['percentage'] = 0
        
        context.update({
            'country_stats': country_stats,
            'total_cbm_all': total_cbm_all,
            'total_orders_with_cbm': total_orders_with_cbm,
            'total_cbm_records': total_cbm_records,
            'date_from': date_from.strftime('%Y-%m-%d') if date_from else '',
            'date_to': date_to.strftime('%Y-%m-%d') if date_to else '',
        })
        
        return context
