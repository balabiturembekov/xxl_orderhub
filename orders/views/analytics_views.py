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
            # Получаем параметры фильтрации по датам из GET запроса
            date_from = self.request.GET.get('date_from')
            date_to = self.request.GET.get('date_to')
            
            # Конвертируем даты если они переданы
            if date_from:
                try:
                    date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                except (ValueError, AttributeError):
                    date_from = None
            else:
                date_from = None  # По умолчанию - все заказы (без ограничения по дате)
            
            if date_to:
                try:
                    date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                except (ValueError, AttributeError):
                    date_to = None
            else:
                date_to = None  # По умолчанию - до текущей даты
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Передаем параметры дат в get_analytics_data
            # Если даты не указаны, будут показаны все заказы (или за большой период)
            analytics_data = get_analytics_data(
                user=self.request.user,
                date_from=date_from,
                date_to=date_to
            )
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
    # Получаем параметры фильтрации по датам из GET запроса
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Конвертируем даты если они переданы
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        except (ValueError, AttributeError):
            date_from = None
    else:
        date_from = None
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        except (ValueError, AttributeError):
            date_to = None
    else:
        date_to = None
    
    # Get analytics data with date filters
    analytics_data = get_analytics_data(
        user=request.user,
        date_from=date_from,
        date_to=date_to
    )
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="analytics_export.csv"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow(['Metric', 'Value'])
    
    # Write data
    overview = analytics_data.get('overview', {})
    writer.writerow(['Total Orders', overview.get('total_orders', 0)])
    writer.writerow(['Orders by Status'])
    writer.writerow(['  uploaded', overview.get('uploaded', 0)])
    writer.writerow(['  sent', overview.get('sent', 0)])
    writer.writerow(['  invoice_received', overview.get('invoice_received', 0)])
    writer.writerow(['  completed', overview.get('completed', 0)])
    writer.writerow(['  cancelled', overview.get('cancelled', 0)])
    
    writer.writerow(['Orders by Factory'])
    factory_stats = analytics_data.get('factory_stats', [])
    for factory_stat in factory_stats:
        factory_name = factory_stat.get('factory__name', 'Unknown')
        writer.writerow([f'  {factory_name}', factory_stat.get('total_orders', 0)])
    
    writer.writerow(['Orders by Country'])
    country_stats = analytics_data.get('country_stats', [])
    for country_stat in country_stats:
        country_name = country_stat.get('factory__country__name', 'Unknown')
        writer.writerow([f'  {country_name}', country_stat.get('total_orders', 0)])
    
    return response


@login_required
def analytics_api(request):
    """
    API endpoint for analytics data in JSON format.
    
    Used by JavaScript charts and graphs on the frontend.
    
    Returns:
        JsonResponse with analytics data
    """
    # Получаем параметры фильтрации по датам из GET запроса
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    # Конвертируем даты если они переданы
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
        except (ValueError, AttributeError):
            date_from = None
    else:
        date_from = None
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
        except (ValueError, AttributeError):
            date_to = None
    else:
        date_to = None
    
    # Get analytics data with date filters
    analytics_data = get_analytics_data(
        user=request.user,
        date_from=date_from,
        date_to=date_to
    )
    
    # Format data for charts
    overview = analytics_data.get('overview', {})
    factory_stats = analytics_data.get('factory_stats', [])
    country_stats = analytics_data.get('country_stats', [])
    time_series = analytics_data.get('time_series', [])
    kpi_metrics = analytics_data.get('kpi_metrics', {})
    
    chart_data = {
        'orders_by_status': {
            'labels': ['uploaded', 'sent', 'invoice_received', 'completed', 'cancelled'],
            'data': [
                overview.get('uploaded', 0),
                overview.get('sent', 0),
                overview.get('invoice_received', 0),
                overview.get('completed', 0),
                overview.get('cancelled', 0)
            ]
        },
        'orders_by_factory': {
            'labels': [stat.get('factory__name', 'Unknown') for stat in factory_stats[:10]],  # Top 10
            'data': [stat.get('total_orders', 0) for stat in factory_stats[:10]]
        },
        'orders_by_country': {
            'labels': [stat.get('factory__country__name', 'Unknown') for stat in country_stats],
            'data': [stat.get('total_orders', 0) for stat in country_stats]
        },
        'monthly_trends': time_series,
        'performance_metrics': kpi_metrics
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
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Исключаем отмененные клиентом заказы
        cbm_queryset = cbm_queryset.filter(order__cancelled_by_client=False)
        
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
            
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к country code и name
            country_code = stat.get('order__factory__country__code') or 'UNKNOWN'
            country_name = stat.get('order__factory__country__name') or 'Не указана'
            
            country_stats.append({
                'country_code': country_code,
                'country_name': country_name,
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
