"""
Authentication views.

This module handles user authentication functionality:
- User registration
- Home page with different content for authenticated/unauthenticated users
- User dashboard
"""

from typing import Dict, Any
from django.shortcuts import render, redirect
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.views.generic import TemplateView, CreateView
from django.urls import reverse_lazy
from django.core.cache import cache
from django.db.models import Q, Count
from django.utils import timezone
from datetime import timedelta

from ..models import Order, Factory, Country


class SignUpView(CreateView):
    """
    User registration view.
    
    Features:
    - User creation form
    - Automatic login after registration
    - Success message
    - Redirect to home page
    """
    form_class = UserCreationForm
    template_name = 'registration/signup.html'
    success_url = reverse_lazy('home')
    
    def form_valid(self, form):
        """Handle successful form submission."""
        response = super().form_valid(form)
        
        # Log the user in automatically
        login(self.request, self.object)
        
        # Create default notification settings
        from ..models import NotificationSettings
        NotificationSettings.objects.create(user=self.object)
        
        messages.success(self.request, f'Добро пожаловать, {self.object.username}!')
        return response


class HomeView(TemplateView):
    """
    Home page view with different content for authenticated and unauthenticated users.
    
    For authenticated users:
    - Personal order statistics
    - Recent orders
    - Quick actions
    
    For unauthenticated users:
    - Public statistics
    - Feature overview
    - Call to action for registration
    """
    template_name = 'orders/home.html'
    
    def get_context_data(self, **kwargs):
        """Add appropriate context data based on user authentication status."""
        context = super().get_context_data(**kwargs)
        context['user'] = self.request.user
        
        if self.request.user.is_authenticated:
            # Add authenticated user context
            context.update(self._get_authenticated_user_context())
        else:
            # Add unauthenticated user context
            context.update(self._get_unauthenticated_user_context())
        
        return context
    
    def _get_authenticated_user_context(self) -> Dict[str, Any]:
        """
        Get context data for authenticated users.
        
        Returns:
            Dictionary with user-specific data
        """
        # Cache user statistics for 5 minutes
        cache_key = f"user_stats_{self.request.user.id}"
        cached_stats = cache.get(cache_key)
        
        if cached_stats is None:
            cached_stats = self._calculate_user_statistics()
            cache.set(cache_key, cached_stats, 300)  # 5 minutes
        
        return cached_stats
    
    def _get_unauthenticated_user_context(self) -> Dict[str, Any]:
        """
        Get context data for unauthenticated users.
        
        Returns:
            Dictionary with public statistics
        """
        # Cache public statistics for 10 minutes
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
    
    def _calculate_user_statistics(self) -> Dict[str, Any]:
        """
        Calculate comprehensive statistics for the authenticated user.
        
        Returns:
            Dictionary with user statistics
        """
        now = timezone.now()
        week_ago = now - timedelta(days=7)
        
        # Get user orders with optimized query
        user_orders = Order.objects.filter(employee=self.request.user)
        
        # Calculate status statistics
        status_stats = user_orders.aggregate(
            uploaded=Count('id', filter=Q(status='uploaded')),
            sent=Count('id', filter=Q(status='sent')),
            invoice_received=Count('id', filter=Q(status='invoice_received')),
            completed=Count('id', filter=Q(status='completed')),
            cancelled=Count('id', filter=Q(status='cancelled')),
        )
        
        # Calculate recent activity
        recent_orders = user_orders.filter(uploaded_at__gte=week_ago).count()
        
        # Get recent orders for display
        recent_orders_list = user_orders.select_related('factory', 'factory__country').order_by('-uploaded_at')[:5]
        
        # Get urgent orders (uploaded more than 3 days ago and still not sent)
        three_days_ago = now - timedelta(days=3)
        urgent_orders_list = user_orders.filter(
            status='uploaded',
            uploaded_at__lt=three_days_ago
        ).select_related('factory', 'factory__country').order_by('uploaded_at')[:5]
        
        # Count overdue orders
        overdue_orders_count = urgent_orders_list.count()
        
        # Calculate factory statistics
        factory_stats = user_orders.values('factory__name', 'factory__country__name').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        # Calculate country statistics
        country_stats = user_orders.values('factory__country__name').annotate(
            count=Count('id')
        ).order_by('-count')[:5]
        
        return {
            'total_orders': user_orders.count(),
            'uploaded_orders': status_stats['uploaded'],
            'sent_orders': status_stats['sent'],
            'completed_orders': status_stats['completed'],
            'cancelled_orders': status_stats['cancelled'],
            'status_stats': status_stats,
            'recent_orders_count': recent_orders,
            'recent_orders': recent_orders_list,
            'urgent_orders': urgent_orders_list,
            'overdue_orders': overdue_orders_count,
            'factory_stats': factory_stats,
            'country_stats': country_stats,
            'week_ago': week_ago,
        }
