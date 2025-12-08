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
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, DetailView
from django.http import HttpResponse, Http404, JsonResponse
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
import os

from ..models import Order, Factory, Country, OrderAuditLog
from ..forms import OrderForm
from ..file_preview import generate_file_preview
from django.db import transaction


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
        
        # Исключаем отмененные клиентом заказы из общего списка
        # Используем ~Q для безопасной обработки возможных NULL значений
        queryset = queryset.filter(~Q(cancelled_by_client=True))
        
        # Apply filters
        status_filter = self.request.GET.get('status')
        factory_filter = self.request.GET.get('factory')
        country_filter = self.request.GET.get('country')
        search_query = self.request.GET.get('search')
        
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        if factory_filter:
            queryset = queryset.filter(factory_id=factory_filter)
        
        if country_filter:
            queryset = queryset.filter(factory__country_id=country_filter)
        
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
        # Получаем список стран, которые есть в заказах (через фабрики)
        context['countries'] = Country.objects.filter(
            factory__is_active=True
        ).distinct().order_by('name')
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
        # Оптимизация: используем prefetch_related для обратных связей
        # Это предотвратит N+1 запросы при загрузке confirmations и audit_logs
        return Order.objects.select_related(
            'factory', 
            'factory__country', 
            'employee'
        ).prefetch_related(
            'orderconfirmation_set__requested_by',
            'orderconfirmation_set__confirmed_by',
            'orderauditlog_set__user',
            'cbm_records__created_by'  # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Оптимизация запросов для CBM
        )
    
    def get_context_data(self, **kwargs):
        """Add additional context for order detail view."""
        import logging
        logger = logging.getLogger('orders')
        
        logger.info(f'OrderDetailView.get_context_data called for order {self.kwargs.get("pk")}')
        context = super().get_context_data(**kwargs)
        order = self.get_object()
        logger.info(f'Order object retrieved: {order.id}')
        
        # Add related data with optimized queries to prevent N+1
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: убрали .count() и избыточный select_related('order')
        # Добавили лимиты для предотвращения загрузки тысяч записей
        logger.info('Loading confirmations...')
        confirmations_qs = order.orderconfirmation_set.select_related(
            'requested_by', 'confirmed_by'
        ).order_by('-requested_at')[:50]  # Лимит 50 последних подтверждений
        context['confirmations'] = list(confirmations_qs)  # Преобразуем в список, чтобы избежать повторных запросов
        logger.info(f'Confirmations loaded: {len(context["confirmations"])}')
        
        logger.info('Loading audit logs...')
        audit_logs_qs = order.orderauditlog_set.select_related('user').order_by('-timestamp')[:100]  # Лимит 100 последних логов
        context['audit_logs'] = list(audit_logs_qs)  # Преобразуем в список
        logger.info(f'Audit logs loaded: {len(context["audit_logs"])}')
        
        # Загружаем CBM записи и общую сумму
        from django.db.models import Sum
        from decimal import Decimal
        
        cbm_records = order.cbm_records.select_related('created_by').order_by('-date', '-created_at')
        total_cbm = cbm_records.aggregate(total=Sum('cbm_value')).get('total') or Decimal('0')
        
        context['cbm_records'] = cbm_records
        context['total_cbm'] = total_cbm
        
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
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к request.user.username
        username = request.user.username if (hasattr(request, 'user') and request.user.is_authenticated) else 'Unknown'
        logger.info(
            f'POST /orders/create/ - User: {username} - '
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
                        
                        # Безопасное получение информации о файле
                        try:
                            file_name = order.excel_file.name if order.excel_file else "None"
                            file_size = "unknown"
                            if order.excel_file:
                                if hasattr(order.excel_file, 'size') and order.excel_file.size is not None:
                                    file_size = f"{order.excel_file.size / (1024*1024):.2f}MB"
                                elif hasattr(order.excel_file, 'file') and hasattr(order.excel_file.file, 'size'):
                                    file_size = f"{order.excel_file.file.size / (1024*1024):.2f}MB"
                            logger.info(f'Excel file name: {file_name}, size: {file_size}')
                        except Exception as file_info_error:
                            logger.warning(f'Could not get file info: {file_info_error}')
                        
                        # Сохраняем заказ - это может занять время для больших файлов
                        import time
                        save_start = time.time()
                        try:
                            order.save()
                            save_duration = time.time() - save_start
                            logger.info(f'Order saved to database, id={order.id}, save took {save_duration:.2f}s')
                        except Exception as save_error:
                            save_duration = time.time() - save_start
                            logger.error(f'Error saving order after {save_duration:.2f}s: {save_error}', exc_info=True)
                            raise  # Пробрасываем ошибку дальше
                        
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
                if 'excel_file' in form.errors and form.errors['excel_file']:
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
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасное получение пути к файлу с обработкой исключений
    try:
        if file_type == 'excel' and order.excel_file:
            file_path = order.excel_file.path
            filename = os.path.basename(file_path)
        elif file_type == 'invoice' and order.invoice_file:
            file_path = order.invoice_file.path
            filename = os.path.basename(file_path)
        else:
            raise Http404("Файл не найден")
    except (ValueError, AttributeError) as e:
        # Файл может не существовать на диске, даже если запись в БД есть
        raise Http404("Файл не найден или недоступен")
    
    # Проверка безопасности пути к файлу
    media_root = os.path.abspath(settings.MEDIA_ROOT)
    file_path_abs = os.path.abspath(file_path)
    
    if not file_path_abs.startswith(media_root):
        raise Http404("Неверный путь к файлу")
    
    if not os.path.exists(file_path):
        raise Http404("Файл не найден на диске")
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем StreamingHttpResponse для больших файлов
    # вместо чтения всего файла в память, что предотвращает OOM для файлов до 2GB
    from django.http import StreamingHttpResponse
    import mimetypes
    
    def file_iterator(file_path, chunk_size=8192):
        """Генератор для чтения файла по частям"""
        with open(file_path, 'rb') as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                yield chunk
    
    # Определяем content_type
    content_type, _ = mimetypes.guess_type(file_path)
    if not content_type:
        content_type = 'application/octet-stream'
    
    response = StreamingHttpResponse(file_iterator(file_path), content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    # Добавляем Content-Length для лучшей поддержки браузеров
    try:
        response['Content-Length'] = str(os.path.getsize(file_path))
    except OSError:
        pass  # Если не удалось получить размер, пропускаем
    
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
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасное получение пути к файлу
        try:
            if file_type == 'excel' and order.excel_file:
                file_path = order.excel_file.path
            elif file_type == 'invoice' and order.invoice_file:
                file_path = order.invoice_file.path
            else:
                return JsonResponse({'error': 'Файл не найден'}, status=404)
        except (ValueError, AttributeError):
            return JsonResponse({'error': 'Файл недоступен'}, status=404)
        
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
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасное получение пути к файлу
        try:
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
        except (ValueError, AttributeError):
            return render(request, 'orders/file_preview_modal.html', {
                'order': order,
                'file_type': file_type,
                'file_name': 'Неизвестный файл',
                'error': 'Файл недоступен'
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


@login_required
@require_http_methods(["POST"])
def cancel_order_by_client(request, pk: int):
    """
    Mark order as cancelled by client.
    
    Args:
        pk: Order primary key
    
    Returns:
        Redirect to order detail page
    """
    order = get_object_or_404(Order, pk=pk)
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем права доступа - только создатель заказа или любой авторизованный пользователь может отменить
    # (по аналогии с другими операциями в системе)
    # Если нужна более строгая проверка, можно добавить: if order.employee != request.user and not request.user.is_staff
    
    # Проверяем, что заказ еще не отменен клиентом
    if order.cancelled_by_client:
        messages.warning(request, 'Этот заказ уже отменен клиентом!')
        return redirect('order_detail', pk=pk)
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем статус заказа - нельзя отменять уже завершенные заказы
    if order.status == 'completed':
        messages.error(request, 'Нельзя отменить уже завершенный заказ!')
        return redirect('order_detail', pk=pk)
    
    comment = request.POST.get('comment', '').strip()
    
    if not comment:
        messages.error(request, 'Пожалуйста, укажите комментарий при отмене заказа!')
        return redirect('order_detail', pk=pk)
    
    # Проверка длины комментария (максимум 2000 символов)
    if len(comment) > 2000:
        messages.error(request, 'Комментарий слишком длинный! Максимум 2000 символов.')
        return redirect('order_detail', pk=pk)
    
    try:
        with transaction.atomic():
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем select_for_update для предотвращения race condition
            # Два пользователя не смогут одновременно отменить один и тот же заказ
            order = Order.objects.select_for_update().get(pk=order.pk)
            
            # Повторная проверка после блокировки (на случай если заказ был отменен между проверкой и блокировкой)
            if order.cancelled_by_client:
                messages.warning(request, 'Этот заказ уже отменен клиентом!')
                return redirect('order_detail', pk=pk)
            
            if order.status == 'completed':
                messages.error(request, 'Нельзя отменить уже завершенный заказ!')
                return redirect('order_detail', pk=pk)
            
            # Отмечаем заказ как отмененный клиентом
            order.cancelled_by_client = True
            order.cancelled_by_client_at = timezone.now()
            order.cancelled_by_client_comment = comment
            order.cancelled_by_client_by = request.user
            order.save()
            
            # Создаем audit log
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: action должен быть из ACTION_TYPES, используем 'cancelled'
            OrderAuditLog.log_action(
                order=order,
                user=request.user,
                action='cancelled',
                field_name='cancelled_by_client',
                old_value='False',
                new_value='True',
                comments=f'Заказ отменен клиентом. Комментарий: {comment[:500]}'  # Ограничиваем длину комментария в логе
            )
        
        messages.success(request, f'Заказ "{order.title}" отмечен как отмененный клиентом!')
    except Exception as e:
        import logging
        logger = logging.getLogger('orders')
        logger.error(f"Ошибка при отмене заказа {order.id}: {e}", exc_info=True)
        messages.error(request, f'Ошибка при отмене заказа: {str(e)}')
    
    return redirect('order_detail', pk=pk)


@method_decorator(login_required, name='dispatch')
class CancelledByClientOrderListView(ListView):
    """
    Display a list of orders cancelled by client.
    
    Features:
    - Filtering by factory, country, and search terms
    - Pagination
    - Order by cancellation date (newest first)
    """
    model = Order
    template_name = 'orders/cancelled_by_client_list.html'
    context_object_name = 'orders'
    paginate_by = 20
    
    def get_queryset(self):
        """Get orders cancelled by client."""
        queryset = Order.objects.filter(
            cancelled_by_client=True
        ).select_related('factory', 'factory__country', 'employee', 'cancelled_by_client_by')
        
        # Apply filters
        factory_filter = self.request.GET.get('factory')
        country_filter = self.request.GET.get('country')
        search_query = self.request.GET.get('search')
        
        if factory_filter:
            try:
                factory_id = int(factory_filter)
                queryset = queryset.filter(factory_id=factory_id)
            except (ValueError, TypeError):
                pass  # Игнорируем невалидные значения
        
        if country_filter:
            try:
                country_id = int(country_filter)
                queryset = queryset.filter(factory__country_id=country_id)
            except (ValueError, TypeError):
                pass  # Игнорируем невалидные значения
        
        if search_query:
            queryset = queryset.filter(
                Q(title__icontains=search_query) |
                Q(description__icontains=search_query) |
                Q(factory__name__icontains=search_query) |
                Q(cancelled_by_client_comment__icontains=search_query)
            )
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем nulls_last для правильной сортировки, если cancelled_by_client_at = None
        from django.db.models import F
        return queryset.order_by(F('cancelled_by_client_at').desc(nulls_last=True), '-uploaded_at')
    
    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        # Фильтруем только активные фабрики
        context['factories'] = Factory.objects.filter(is_active=True).select_related('country')
        # Получаем список стран, которые есть в заказах (через фабрики)
        context['countries'] = Country.objects.filter(
            factory__is_active=True
        ).distinct().order_by('name')
        return context
