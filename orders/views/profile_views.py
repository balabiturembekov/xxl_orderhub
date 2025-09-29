"""
Представления для управления профилем пользователя.

Этот модуль содержит представления для:
- Просмотра профиля пользователя
- Редактирования профиля
- Изменения email
- Управления настройками уведомлений
"""

from typing import Dict, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.views.generic import TemplateView
from django.utils.decorators import method_decorator
from django.urls import reverse_lazy
from ..forms import UserProfileForm, UserEmailForm
from ..models import UserProfile


@method_decorator(login_required, name='dispatch')
class ProfileView(TemplateView):
    """
    Представление для просмотра профиля пользователя.
    
    Отображает:
    - Основную информацию пользователя
    - Профиль пользователя
    - Статистику активности
    """
    template_name = 'orders/profile.html'
    
    def get_context_data(self, **kwargs) -> Dict[str, Any]:
        """
        Получает контекстные данные для шаблона.
        
        Returns:
            Dict[str, Any]: Контекстные данные
        """
        context = super().get_context_data(**kwargs)
        user = self.request.user
        
        # Получаем или создаем профиль пользователя
        profile, created = UserProfile.objects.get_or_create(user=user)
        
        # Статистика пользователя
        from ..models import Order, Notification
        user_orders = Order.objects.all()
        user_notifications = Notification.objects.filter(user=user)
        
        context.update({
            'profile': profile,
            'user_orders_count': user_orders.count(),
            'user_notifications_count': user_notifications.count(),
            'unread_notifications_count': user_notifications.filter(is_read=False).count(),
            'recent_orders': user_orders.select_related('factory', 'factory__country', 'employee').order_by('-uploaded_at')[:5],
            'recent_notifications': user_notifications.order_by('-created_at')[:5],
        })
        
        return context


@login_required
def edit_profile(request):
    """
    Представление для редактирования профиля пользователя.
    
    Обрабатывает:
    - GET: Отображение формы редактирования
    - POST: Сохранение изменений профиля
    
    Returns:
        HttpResponse: Страница редактирования или редирект
    """
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Профиль успешно обновлен!')
            return redirect('profile')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'orders/edit_profile.html', {
        'form': form,
        'profile': profile
    })


@login_required
def change_email(request):
    """
    Представление для изменения email пользователя.
    
    Обрабатывает:
    - GET: Отображение формы изменения email
    - POST: Сохранение нового email
    
    Returns:
        HttpResponse: Страница изменения email или редирект
    """
    if request.method == 'POST':
        form = UserEmailForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Email успешно изменен!')
            return redirect('profile')
    else:
        form = UserEmailForm(instance=request.user)
    
    return render(request, 'orders/change_email.html', {
        'form': form
    })


@login_required
def profile_settings(request):
    """
    Представление для настроек профиля.
    
    Объединяет все настройки профиля в одном месте:
    - Редактирование профиля
    - Изменение email
    - Настройки уведомлений
    
    Returns:
        HttpResponse: Страница настроек профиля
    """
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    # Формы для разных разделов
    profile_form = UserProfileForm(instance=profile)
    email_form = UserEmailForm(instance=request.user)
    
    # Настройки уведомлений
    from ..models import NotificationSettings
    try:
        notification_settings = NotificationSettings.objects.get(user=request.user)
    except NotificationSettings.DoesNotExist:
        notification_settings = NotificationSettings.objects.create(user=request.user)
    
    return render(request, 'orders/profile_settings.html', {
        'profile': profile,
        'profile_form': profile_form,
        'email_form': email_form,
        'notification_settings': notification_settings,
    })
