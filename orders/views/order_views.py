"""
Order management views.

This module contains all views related to order CRUD operations:
- Order listing and filtering
- Order creation and editing
- Order detail view
- File upload and download
- Order status management
"""

from typing import Dict, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView
from django.http import HttpResponse, Http404, JsonResponse
from django.utils import timezone
from django.db.models import Q
import os

from ..models import Order, Factory
from ..forms import OrderForm
from ..file_preview import generate_file_preview


@method_decorator(login_required, name='dispatch')
class OrderListView(ListView):
    """
    Display a list of orders for the authenticated user.
    
    Features:
    - Filtering by status, factory, and search terms
    - Pagination
    - Order by upload date (newest first)
    """
    model = Order
    template_name = 'orders/order_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        """Get filtered orders for all users."""
        queryset = Order.objects.select_related('factory', 'factory__country', 'employee')
        
        # Apply filters
        status_filter = self.request.GET.get('status')
        factory_filter = self.request.GET.get('factory')
        search_query = self.request.GET.get('search')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if factory_filter:
            queryset = queryset.filter(factory_id=factory_filter)
        
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(factory__name__icontains=search_query)
            )
        
        return queryset.order_by('-uploaded_at')
    
    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        context['factories'] = Factory.objects.select_related('country')
        context['status_choices'] = Order.STATUS_CHOICES
        return context


@method_decorator(login_required, name='dispatch')
class OrderDetailView(DetailView):
    """
    Display detailed information about a specific order.
    
    Features:
    - Order information display
    - File preview capabilities
    - Action buttons based on order status
    - Related confirmations and audit logs
    """
    model = Order
    template_name = 'orders/order_detail.html'
    context_object_name = 'order'
    
    def get_queryset(self):
        """Show all orders."""
        return Order.objects.select_related('factory', 'factory__country', 'employee')
    
    def get_context_data(self, **kwargs):
        """Add additional context for order detail view."""
        context = super().get_context_data(**kwargs)
        order = self.get_object()
        
        # Add related data
        context['confirmations'] = order.orderconfirmation_set.all().order_by('-requested_at')
        context['audit_logs'] = order.orderauditlog_set.all().order_by('-timestamp')
        
        # Calculate days since upload/sent
        if order.uploaded_at:
            context['days_since_upload'] = (timezone.now() - order.uploaded_at).days
        
        if order.sent_at:
            context['days_since_sent'] = (timezone.now() - order.sent_at).days
        
        return context


@login_required
def create_order(request):
    """
    Create a new order.
    
    Handles both GET (show form) and POST (process form) requests.
    Creates order with uploaded Excel file and associates it with the current user.
    """
    if request.method == 'POST':
        form = OrderForm(request.POST, request.FILES)
        if form.is_valid():
            order = form.save(commit=False)
            order.employee = request.user
            order.save()
            
            messages.success(request, f'Заказ "{order.title}" успешно создан!')
            return redirect('order_detail', pk=order.pk)
    else:
        form = OrderForm()
    
    return render(request, 'orders/order_form.html', {'form': form})


@login_required
def download_file(request, pk: int, file_type: str):
    """
    Download order files (Excel or PDF invoice).
    
    Args:
        pk: Order primary key
        file_type: Type of file to download ('excel' or 'invoice')
    
    Returns:
        HttpResponse with file content or 404 if file not found
    """
    order = get_object_or_404(Order, pk=pk)
    
    if file_type == 'excel' and order.excel_file:
        file_path = order.excel_file.path
        filename = os.path.basename(file_path)
    elif file_type == 'invoice' and order.invoice_file:
        file_path = order.invoice_file.path
        filename = os.path.basename(file_path)
    else:
        raise Http404("Файл не найден")
    
    if not os.path.exists(file_path):
        raise Http404("Файл не найден на диске")
    
    with open(file_path, 'rb') as file:
        response = HttpResponse(file.read(), content_type='application/octet-stream')
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response


@login_required
def preview_file(request, pk: int, file_type: str):
    """
    Generate and return file preview for modal display.
    
    Args:
        pk: Order primary key
        file_type: Type of file to preview ('excel' or 'invoice')
    
    Returns:
        JsonResponse with preview data or error message
    """
    order = get_object_or_404(Order, pk=pk)
    
    try:
        # Get file path based on file type
        if file_type == 'excel' and order.excel_file:
            file_path = order.excel_file.path
        elif file_type == 'invoice' and order.invoice_file:
            file_path = order.invoice_file.path
        else:
            return JsonResponse({'error': 'Файл не найден'}, status=404)
        
        preview_data = generate_file_preview(file_path, file_type)
        return JsonResponse(preview_data)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def preview_file_modal(request, pk: int, file_type: str):
    """
    Display file preview in modal window.
    
    Args:
        pk: Order primary key
        file_type: Type of file to preview ('excel' or 'invoice')
    
    Returns:
        Rendered modal template with preview data
    """
    order = get_object_or_404(Order, pk=pk)
    
    try:
        # Get file path based on file type
        if file_type == 'excel' and order.excel_file:
            file_path = order.excel_file.path
        elif file_type == 'invoice' and order.invoice_file:
            file_path = order.invoice_file.path
        else:
            return render(request, 'orders/file_preview_modal.html', {
                'order': order,
                'file_type': file_type,
                'file_name': 'Неизвестный файл',
                'error': 'Файл не найден'
            })
        
        preview_data = generate_file_preview(file_path, file_type)
        file_name = os.path.basename(file_path)
        return render(request, 'orders/file_preview_modal.html', {
            'order': order,
            'file_type': file_type,
            'file_name': file_name,
            'preview_data': preview_data
        })
    except Exception as e:
        return render(request, 'orders/file_preview_modal.html', {
            'order': order,
            'file_type': file_type,
            'file_name': 'Неизвестный файл',
            'error': str(e)
        })
