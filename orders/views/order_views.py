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
from django.conf import settings
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
        # Фильтруем только активные фабрики
        context['factories'] = Factory.objects.filter(is_active=True).select_related('country')
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
        import logging
        logger = logging.getLogger('orders')
        
        logger.info(f'OrderDetailView.get_context_data called for order {self.kwargs.get("pk")}')
        context = super().get_context_data(**kwargs)
        order = self.get_object()
        logger.info(f'Order object retrieved: {order.id}')
        
        # Add related data with optimized queries to prevent N+1
        logger.info('Loading confirmations...')
        context['confirmations'] = order.orderconfirmation_set.select_related(
            'requested_by', 'confirmed_by', 'order'
        ).order_by('-requested_at')
        logger.info(f'Confirmations loaded: {context["confirmations"].count()}')
        
        logger.info('Loading audit logs...')
        context['audit_logs'] = order.orderauditlog_set.select_related('user', 'order').order_by('-timestamp')
        logger.info(f'Audit logs loaded: {context["audit_logs"].count()}')
        
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
    import logging
    from django.db import transaction
    from ..models import OrderAuditLog
    
    logger = logging.getLogger('orders')
    
    if request.method == 'POST':
        # Логируем сразу при получении POST запроса
        file_size = 0
        if 'excel_file' in request.FILES:
            file_size = request.FILES['excel_file'].size
        logger.info(
            f'POST /orders/create/ - User: {request.user.username} - '
            f'IP: {request.META.get("REMOTE_ADDR")} - '
            f'File size: {file_size / (1024*1024):.2f}MB'
        )
        try:
            logger.info('Creating form instance...')
            form = OrderForm(request.POST, request.FILES)
            logger.info('Form instance created, starting validation...')
            if form.is_valid():
                logger.info(f'Form is valid, saving order...')
                try:
                    # Используем транзакцию для атомарности операции
                    with transaction.atomic():
                        logger.info('Starting order save...')
                        order = form.save(commit=False)
                        order.employee = request.user
                        # Убеждаемся, что invoice_file не установлен при создании
                        if order.invoice_file:
                            order.invoice_file = None
                        
                        # Сохраняем заказ (файл будет сохранен на диск здесь)
                        logger.info(f'Saving order to database, factory_id={order.factory_id}...')
                        order.save()
                        logger.info(f'Order saved to database, id={order.id}')
                        
                        # Создаем аудит-лог
                        logger.info('Creating audit log...')
                        OrderAuditLog.log_action(
                            order=order,
                            user=request.user,
                            action='created',
                            field_name='order',
                            comments=f'Заказ "{order.title}" создан пользователем {request.user.username}'
                        )
                        logger.info('Audit log created')
                        
                        logger.info(f'Order created successfully: {order.id} by user {request.user.username}')
                        messages.success(request, f'Заказ "{order.title}" успешно создан!')
                        
                        # Логируем перед redirect для диагностики
                        logger.info(f'About to redirect to order_detail for order {order.id}')
                        try:
                            redirect_url = redirect('order_detail', pk=order.pk)
                            logger.info(f'Redirect URL created successfully: {redirect_url.url if hasattr(redirect_url, "url") else "OK"}')
                            return redirect_url
                        except Exception as redirect_error:
                            logger.error(f'Error creating redirect: {redirect_error}', exc_info=True)
                            # Fallback: redirect to order list if detail fails
                            return redirect('order_list')
                except Exception as e:
                    logger.error(f'Error saving order: {e}', exc_info=True)
                    messages.error(request, f'Ошибка при сохранении заказа: {str(e)}')
            else:
                # Логируем ошибки валидации
                logger.warning(f'Order form validation failed: {form.errors}')
                if 'excel_file' in form.errors:
                    messages.error(request, f'Ошибка в файле: {form.errors["excel_file"][0]}')
                elif 'factory' in form.errors:
                    messages.error(request, 'Пожалуйста, выберите фабрику.')
                else:
                    messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
        except Exception as e:
            logger.error(f'Unexpected error in create_order: {e}', exc_info=True)
            messages.error(request, 'Произошла неожиданная ошибка при создании заказа. Обратитесь к администратору.')
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
    # Валидация file_type для предотвращения path traversal
    if file_type not in ['excel', 'invoice']:
        raise Http404("Неверный тип файла")
    
    order = get_object_or_404(Order, pk=pk)
    
    if file_type == 'excel' and order.excel_file:
        file_path = order.excel_file.path
        filename = os.path.basename(file_path)
    elif file_type == 'invoice' and order.invoice_file:
        file_path = order.invoice_file.path
        filename = os.path.basename(file_path)
    else:
        raise Http404("Файл не найден")
    
    # Проверка безопасности пути к файлу
    media_root = os.path.abspath(settings.MEDIA_ROOT)
    file_path_abs = os.path.abspath(file_path)
    
    if not file_path_abs.startswith(media_root):
        raise Http404("Неверный путь к файлу")
    
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
    # Валидация file_type для предотвращения path traversal
    if file_type not in ['excel', 'invoice']:
        return JsonResponse({'error': 'Неверный тип файла'}, status=400)
    
    order = get_object_or_404(Order, pk=pk)
    
    try:
        # Get file path based on file type
        if file_type == 'excel' and order.excel_file:
            file_path = order.excel_file.path
        elif file_type == 'invoice' and order.invoice_file:
            file_path = order.invoice_file.path
        else:
            return JsonResponse({'error': 'Файл не найден'}, status=404)
        
        # Проверка безопасности пути к файлу
        media_root = os.path.abspath(settings.MEDIA_ROOT)
        file_path_abs = os.path.abspath(file_path)
        
        if not file_path_abs.startswith(media_root):
            return JsonResponse({'error': 'Неверный путь к файлу'}, status=403)
        
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
    # Валидация file_type для предотвращения path traversal
    if file_type not in ['excel', 'invoice']:
        order = get_object_or_404(Order, pk=pk)
        return render(request, 'orders/file_preview_modal.html', {
            'order': order,
            'file_type': file_type,
            'file_name': 'Неизвестный файл',
            'error': 'Неверный тип файла'
        })
    
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
        
        # Проверка безопасности пути к файлу
        media_root = os.path.abspath(settings.MEDIA_ROOT)
        file_path_abs = os.path.abspath(file_path)
        
        if not file_path_abs.startswith(media_root):
            return render(request, 'orders/file_preview_modal.html', {
                'order': order,
                'file_type': file_type,
                'file_name': 'Неизвестный файл',
                'error': 'Неверный путь к файлу'
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
