"""
Notification management views.

This module handles all notification-related functionality:
- Notification listing and filtering
- Marking notifications as read
- Notification settings management
- Testing notification system
"""

from typing import Dict, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Q

from ..models import Notification, NotificationSettings, Order
from ..forms import NotificationSettingsForm, NotificationFilterForm
from ..tasks import send_order_notification


@method_decorator(login_required, name='dispatch')
class NotificationListView(ListView):
    """
    Display a list of notifications for the authenticated user.
    
    Features:
    - Filtering by read/unread status
    - Pagination
    - Order by creation date (newest first)
    """
    model = Notification
    template_name = 'orders/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        """Get notifications for the current user."""
        queryset = Notification.objects.filter(user=self.request.user).order_by('-created_at')
        
        # Apply filters
        status_filter = self.request.GET.get('status')
        type_filter = self.request.GET.get('notification_type')
        search_query = self.request.GET.get('search')
        
        # Status filter
        if status_filter == 'unread':
            queryset = queryset.filter(is_read=False)
        elif status_filter == 'read':
            queryset = queryset.filter(is_read=True)
        
        # Type filter
        if type_filter:
            queryset = queryset.filter(notification_type=type_filter)
        
        # Search filter
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(message__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        
        # Create filter form with current GET parameters
        form = NotificationFilterForm(self.request.GET)
        context['form'] = form
        
        # Add filter values
        context['status_filter'] = self.request.GET.get('status', '')
        context['type_filter'] = self.request.GET.get('notification_type', '')
        context['search_query'] = self.request.GET.get('search', '')
        
        # Add counts
        context['unread_count'] = Notification.objects.filter(
            user=self.request.user, 
            is_read=False
        ).count()
        context['total_count'] = Notification.objects.filter(
            user=self.request.user
        ).count()
        
        return context


@login_required
def mark_notification_read(request, pk: int):
    """
    Mark a specific notification as read.
    
    Args:
        pk: Notification primary key
    
    Returns:
        JsonResponse with success status
    """
    notification = get_object_or_404(Notification, pk=pk, user=request.user)
    
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save()
        
        return JsonResponse({'success': True, 'message': 'Уведомление отмечено как прочитанное'})
    else:
        return JsonResponse({'success': False, 'message': 'Уведомление уже прочитано'})


@login_required
def mark_all_notifications_read(request):
    """
    Mark all notifications for the current user as read.
    
    Returns:
        JsonResponse with success status and count of marked notifications
    """
    unread_notifications = Notification.objects.filter(
        user=request.user, 
        is_read=False
    )
    
    count = unread_notifications.count()
    
    if count > 0:
        unread_notifications.update(
            is_read=True,
            read_at=timezone.now()
        )
        
        return JsonResponse({
            'success': True, 
            'message': f'Отмечено как прочитанные: {count} уведомлений',
            'count': count
        })
    else:
        return JsonResponse({
            'success': False, 
            'message': 'Нет непрочитанных уведомлений'
        })


@login_required
def notification_settings(request):
    """
    Manage notification settings for the current user.
    
    Handles both GET (show settings) and POST (update settings) requests.
    Creates default settings if they don't exist.
    """
    try:
        settings_obj = NotificationSettings.objects.get(user=request.user)
    except NotificationSettings.DoesNotExist:
        # Create default settings if they don't exist
        settings_obj = NotificationSettings.objects.create(user=request.user)
    
    if request.method == 'POST':
        form = NotificationSettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Настройки уведомлений сохранены!')
            return redirect('notification_settings')
    else:
        form = NotificationSettingsForm(instance=settings_obj)
    
    return render(request, 'orders/notification_settings.html', {
        'form': form,
        'settings': settings_obj
    })


@login_required
def test_notification(request):
    """
    Send a test notification to the current user.
    
    This is useful for testing the notification system and email delivery.
    
    Returns:
        Redirect to notification settings with success/error message
    """
    if request.method == 'POST':
        # Get the last order for the user (for testing purposes)
        last_order = Order.objects.filter(employee=request.user).first()
        
        if last_order:
            try:
                # Send test notification
                send_order_notification.delay(last_order.id, 'order_sent')
                messages.success(request, 'Тестовое уведомление отправлено! Проверьте email.')
            except Exception as e:
                messages.error(request, f'Ошибка при отправке тестового уведомления: {str(e)}')
        else:
            messages.warning(request, 'У вас нет заказов для тестирования.')
        
        return redirect('notification_settings')
    
    return redirect('notification_settings')
