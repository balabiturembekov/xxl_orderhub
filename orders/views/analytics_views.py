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

from ..models import Order, Factory, Country
from ..analytics import get_analytics_data


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
                'total_orders': Order.objects.count(),
                'total_factories': Factory.objects.count(),
                'total_countries': Country.objects.count(),
                'active_users': Order.objects.values('employee').distinct().count(),
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
