"""
Views for managing shipments (фуры).

This module contains views for:
- Listing shipments
- Creating new shipments
- Viewing shipment details
- Updating shipments
- Deleting shipments
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.db.models import Sum, Q, F
from django.db import transaction
from django.utils import timezone
from django.http import JsonResponse

from ..models import Shipment, Order, OrderAuditLog
from ..forms import ShipmentForm


@method_decorator(login_required, name='dispatch')
class ShipmentListView(ListView):
    """
    Display a list of shipments.
    
    Features:
    - Filtering by date range
    - Search by shipment number
    - Pagination
    """
    model = Shipment
    template_name = 'orders/shipment_list.html'
    context_object_name = 'shipments'
    paginate_by = 20
    
    def get_paginate_by(self, queryset):
        """
        КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-60: Валидация paginate_by для предотвращения DoS атак.
        Если в будущем будет добавлена возможность изменять размер страницы через параметры,
        это предотвратит очень большие запросы к БД.
        """
        from ..constants import ViewConstants
        
        page_size = self.request.GET.get('page_size', self.paginate_by)
        try:
            page_size = int(page_size)
            if page_size < 1:
                page_size = self.paginate_by
            elif page_size > ViewConstants.MAX_PAGE_SIZE:
                page_size = ViewConstants.MAX_PAGE_SIZE
        except (ValueError, TypeError):
            page_size = self.paginate_by
        return page_size
    
    def get_queryset(self):
        """Get filtered shipments."""
        queryset = Shipment.objects.prefetch_related('orders', 'orders__factory', 'orders__factory__country')
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-49: Валидация длины search_query для предотвращения DoS атак
        from ..constants import ViewConstants
        
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            if len(search_query) > ViewConstants.SEARCH_MAX_LENGTH:
                search_query = search_query[:ViewConstants.SEARCH_MAX_LENGTH]
            
            if len(search_query) >= ViewConstants.SEARCH_MIN_LENGTH:
                queryset = queryset.filter(
                    Q(shipment_number__icontains=search_query) |
                    Q(notes__icontains=search_query)
                )
        
        # Filter by date range
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        
        if date_from:
            try:
                # Валидация формата даты
                from datetime import datetime
                datetime.strptime(date_from, '%Y-%m-%d')
                queryset = queryset.filter(shipment_date__gte=date_from)
            except (ValueError, TypeError):
                # Если дата невалидна, игнорируем фильтр
                pass
        
        if date_to:
            try:
                # Валидация формата даты
                from datetime import datetime
                datetime.strptime(date_to, '%Y-%m-%d')
                queryset = queryset.filter(shipment_date__lte=date_to)
            except (ValueError, TypeError):
                # Если дата невалидна, игнорируем фильтр
                pass
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Сортировка с обработкой None значений
        # Используем F() для корректной сортировки, где None идут в конец
        return queryset.order_by(
            F('shipment_date').desc(nulls_last=True),
            '-created_at'
        )
    
    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        context['search_query'] = self.request.GET.get('search', '')
        context['date_from'] = self.request.GET.get('date_from', '')
        context['date_to'] = self.request.GET.get('date_to', '')
        return context


@method_decorator(login_required, name='dispatch')
class ShipmentDetailView(DetailView):
    """
    Display detailed information about a shipment.
    
    Features:
    - List of orders in shipment
    - CBM statistics (invoice vs received)
    - Difference calculation
    """
    model = Shipment
    template_name = 'orders/shipment_detail.html'
    context_object_name = 'shipment'
    
    def get_queryset(self):
        """Optimize queries."""
        return Shipment.objects.prefetch_related(
            'orders',
            'orders__factory',
            'orders__factory__country',
            'orders__cbm_records',
            'orders__invoice'
        )
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        context = super().get_context_data(**kwargs)
        shipment = self.get_object()
        
        # Calculate statistics for each order
        orders_data = []
        from decimal import Decimal
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-41: Используем annotate для предотвращения N+1 запросов
        # Предварительно вычисляем CBM для всех заказов одним запросом
        orders_with_cbm = shipment.orders.select_related('factory', 'factory__country').annotate(
            total_cbm=Sum('cbm_records__cbm_value')
        )
        
        for order in orders_with_cbm:
            order_cbm = order.total_cbm or Decimal('0')
            
            orders_data.append({
                'order': order,
                'invoice_cbm': order_cbm,
            })
        
        context['orders_data'] = orders_data
        context['total_invoice_cbm'] = shipment.total_invoice_cbm
        context['received_cbm'] = shipment.received_cbm
        context['cbm_difference'] = shipment.cbm_difference
        context['cbm_difference_percentage'] = shipment.cbm_difference_percentage
        
        # Проверка на пустую фуру
        if not orders_data:
            context['empty_shipment'] = True
        
        return context


@method_decorator(login_required, name='dispatch')
class ShipmentCreateView(CreateView):
    """
    Create a new shipment.
    """
    model = Shipment
    form_class = ShipmentForm
    template_name = 'orders/shipment_form.html'
    
    def get_form_kwargs(self):
        """Pass user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Save shipment and create audit log."""
        with transaction.atomic():
            shipment = form.save(commit=False)
            shipment.created_by = self.request.user
            shipment.save()
            form.save_m2m()  # Save ManyToMany relationships
            
            # Create audit log for each order
            for order in shipment.orders.all():
                OrderAuditLog.log_action(
                    order=order,
                    user=self.request.user,
                    action='updated',
                    field_name='shipment',
                    new_value=f'Добавлен в фуру {shipment.shipment_number}',
                    comments=f'Заказ добавлен в фуру {shipment.shipment_number}'
                )
        
        messages.success(
            self.request,
            f'Фура "{shipment.shipment_number}" успешно создана!'
        )
        return redirect('shipment_detail', pk=shipment.pk)


@method_decorator(login_required, name='dispatch')
class ShipmentUpdateView(UpdateView):
    """
    Update an existing shipment.
    """
    model = Shipment
    form_class = ShipmentForm
    template_name = 'orders/shipment_form.html'
    
    def get_form_kwargs(self):
        """Pass user to form."""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        """Save shipment and create audit log."""
        shipment = self.get_object()
        old_orders = set(shipment.orders.all())
        
        with transaction.atomic():
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем save(commit=False) + save() + save_m2m()
            # для корректного сохранения ManyToMany полей
            shipment = form.save(commit=False)
            shipment.save()  # Сохраняем основную модель
            form.save_m2m()  # Сохраняем ManyToMany связи
            
            new_orders = set(shipment.orders.all())
            added_orders = new_orders - old_orders
            removed_orders = old_orders - new_orders
            
            # Create audit logs
            for order in added_orders:
                OrderAuditLog.log_action(
                    order=order,
                    user=self.request.user,
                    action='updated',
                    field_name='shipment',
                    new_value=f'Добавлен в фуру {shipment.shipment_number}',
                    comments=f'Заказ добавлен в фуру {shipment.shipment_number}'
                )
            
            for order in removed_orders:
                OrderAuditLog.log_action(
                    order=order,
                    user=self.request.user,
                    action='updated',
                    field_name='shipment',
                    old_value=f'Был в фуре {shipment.shipment_number}',
                    comments=f'Заказ удален из фуры {shipment.shipment_number}'
                )
        
        messages.success(
            self.request,
            f'Фура "{shipment.shipment_number}" успешно обновлена!'
        )
        return redirect('shipment_detail', pk=shipment.pk)


@method_decorator(login_required, name='dispatch')
class ShipmentDeleteView(DeleteView):
    """
    Delete a shipment.
    """
    model = Shipment
    template_name = 'orders/shipment_confirm_delete.html'
    success_url = '/orders/shipments/'
    
    def delete(self, request, *args, **kwargs):
        """Delete shipment and create audit logs."""
        shipment = self.get_object()
        orders = list(shipment.orders.all())
        
        with transaction.atomic():
            # Create audit logs before deletion
            for order in orders:
                OrderAuditLog.log_action(
                    order=order,
                    user=request.user,
                    action='updated',
                    field_name='shipment',
                    old_value=f'Был в фуре {shipment.shipment_number}',
                    comments=f'Фура {shipment.shipment_number} удалена'
                )
            
            return super().delete(request, *args, **kwargs)
    
    def get_success_url(self):
        """Redirect to shipment list."""
        messages.success(
            self.request,
            f'Фура "{self.object.shipment_number}" успешно удалена!'
        )
        return '/orders/shipments/'

