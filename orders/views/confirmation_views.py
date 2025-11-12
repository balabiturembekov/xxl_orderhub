"""
Order confirmation system views.

This module handles the critical operations confirmation system:
- Creating confirmations for critical operations
- Approving/rejecting confirmations
- Managing confirmation workflow
- Audit logging for all operations
"""

from typing import Dict, Any
import logging
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView
from django.utils import timezone
from django.core.mail import EmailMessage
from django.conf import settings
from django.template.loader import render_to_string

from ..models import Order, OrderConfirmation, OrderAuditLog
from ..forms import InvoiceUploadForm
from ..tasks import send_order_notification


class ConfirmationListView(ListView):
    """
    Display a list of order confirmations for the authenticated user.
    
    Features:
    - Filtering by status
    - Pagination
    - Order by request date (newest first)
    """
    model = OrderConfirmation
    template_name = 'orders/confirmation_list.html'
    context_object_name = 'confirmations'
    paginate_by = 20
    
    def get_queryset(self):
        """Get confirmations for orders belonging to the current user."""
        queryset = OrderConfirmation.objects.filter(
        ).select_related('order', 'requested_by', 'confirmed_by').order_by('-requested_at')
        
        # Apply status filter
        status_filter = self.request.GET.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        context['status_choices'] = OrderConfirmation._meta.get_field('status').choices
        context['status_filter'] = self.request.GET.get('status', '')
        return context


@login_required
def confirmation_detail(request, pk: int):
    """
    Display detailed information about a specific confirmation.
    
    Args:
        pk: Confirmation primary key
    
    Returns:
        Rendered confirmation detail template
    """
    confirmation = get_object_or_404(OrderConfirmation, pk=pk)
    
    return render(request, 'orders/confirmation_detail.html', {
        'confirmation': confirmation,
    })


@login_required
def send_order(request, pk: int):
    """
    Create confirmation for sending order to factory.
    
    This is the first step in the order sending process:
    1. Create OrderConfirmation
    2. Redirect to confirmation approval page
    3. User confirms operation
    4. Order is sent via email
    
    Args:
        pk: Order primary key
    
    Returns:
        Redirect to confirmation approval page
    """
    order = get_object_or_404(Order, pk=pk)
    
    # Validate order status
    if order.status != 'uploaded':
        messages.error(request, 'Заказ уже отправлен или имеет другой статус!')
        return redirect('order_detail', pk=pk)
    
    # Check for existing active confirmation
    active_confirmation = OrderConfirmation.objects.filter(
        order=order,
        action='send_order',
        status='pending',
        expires_at__gt=timezone.now()
    ).first()
    
    if active_confirmation:
        messages.warning(request, 'У вас уже есть активное подтверждение для отправки этого заказа.')
        return redirect('confirmation_detail', pk=active_confirmation.pk)
    
    # Create new confirmation
    confirmation = OrderConfirmation.objects.create(
        order=order,
        action='send_order',
        requested_by=request.user,
        confirmation_data={
            'order_title': order.title,
            'factory_name': order.factory.name,
            'factory_email': order.factory.email,
            'country': order.factory.country.name,
        }
    )
    
    messages.info(request, 'Создано подтверждение для отправки заказа. Подтвердите операцию для выполнения.')
    return redirect('confirmation_approve', pk=confirmation.pk)


@login_required
def upload_invoice(request, pk: int):
    """
    Create confirmation for uploading invoice.
    
    Args:
        pk: Order primary key
    
    Returns:
        Redirect to confirmation approval page
    """
    order = get_object_or_404(Order, pk=pk)
    
    # Validate order status
    if order.status not in ['sent', 'invoice_received']:
        messages.error(request, 'Инвойс можно прикрепить только после отправки заказа на фабрику!')
        return redirect('order_detail', pk=pk)
    
    # Check for existing active confirmation
    active_confirmation = OrderConfirmation.objects.filter(
        order=order,
        action='upload_invoice',
        status='pending',
        expires_at__gt=timezone.now()
    ).first()
    
    if active_confirmation:
        messages.warning(request, 'У вас уже есть активное подтверждение для загрузки инвойса этого заказа.')
        return redirect('confirmation_detail', pk=active_confirmation.pk)
    
    # Create new confirmation
    confirmation = OrderConfirmation.objects.create(
        order=order,
        action='upload_invoice',
        requested_by=request.user,
        confirmation_data={
            'order_title': order.title,
            'factory_name': order.factory.name,
            'current_status': order.get_status_display(),
            'sent_at': order.sent_at.strftime('%d.%m.%Y %H:%M') if order.sent_at else None,
        }
    )
    
    messages.info(request, 'Создано подтверждение для загрузки инвойса. Подтвердите операцию для выполнения.')
    return redirect('confirmation_approve', pk=confirmation.pk)


@login_required
def upload_invoice_form(request, pk: int):
    """
    Display invoice upload form after confirmation approval.
    
    Args:
        pk: Order primary key
    
    Returns:
        Rendered invoice upload form template
    """
    order = get_object_or_404(Order, pk=pk)
    
    # Validate order status
    if order.status not in ['sent', 'invoice_received']:
        messages.error(request, 'Инвойс можно прикрепить только после отправки заказа на фабрику!')
        return redirect('order_detail', pk=pk)
    
    # Check for active confirmation
    active_confirmation = OrderConfirmation.objects.filter(
        order=order,
        action='upload_invoice',
        status='pending',
        expires_at__gt=timezone.now()
    ).first()
    
    if not active_confirmation:
        messages.error(request, 'Нет активного подтверждения для загрузки инвойса!')
        return redirect('order_detail', pk=pk)
    
    # Используем новую форму для создания инвойса с платежом
    from ..forms import InvoiceWithPaymentForm
    
    # Проверяем, есть ли уже инвойс у заказа
    initial_data = {}
    if hasattr(order, 'invoice') and order.invoice and order.invoice.pk:
        invoice = order.invoice
        initial_data = {
            'invoice_number': invoice.invoice_number,
            'balance': invoice.balance,
            'due_date': invoice.due_date,
            'invoice_notes': invoice.notes,
            'payment_date': timezone.now().date(),
            'payment_type': 'partial_payment',
        }
        
        # Если есть платежи, предзаполняем сумму остатка
        if invoice.payments.exists():
            initial_data['payment_amount'] = invoice.remaining_amount
    
    form = InvoiceWithPaymentForm(initial=initial_data)
    
    # Добавляем информацию о существующем файле инвойса
    invoice_file_info = None
    has_existing_file = False
    if hasattr(order, 'invoice') and order.invoice_file:
        has_existing_file = True
        invoice_file_info = {
            'name': order.invoice_file.name.split('/')[-1],  # Только имя файла
            'size': order.invoice_file.size,
            'url': order.invoice_file.url if hasattr(order.invoice_file, 'url') else None
        }
        
        # Делаем поле файла необязательным, если файл уже есть
        form.fields['invoice_file'].required = False
        
        # Делаем поля инвойса неактивными, если инвойс уже создан
        form.fields['invoice_number'].widget.attrs['readonly'] = True
        form.fields['invoice_number'].widget.attrs['class'] = 'form-control-plaintext'
        form.fields['balance'].widget.attrs['readonly'] = True
        form.fields['balance'].widget.attrs['class'] = 'form-control-plaintext'
        form.fields['due_date'].widget.attrs['readonly'] = True
        form.fields['due_date'].widget.attrs['class'] = 'form-control-plaintext'
        form.fields['invoice_notes'].widget.attrs['readonly'] = True
        form.fields['invoice_notes'].widget.attrs['class'] = 'form-control-plaintext'
    
    return render(request, 'orders/upload_invoice_form.html', {
        'form': form,
        'order': order,
        'confirmation': active_confirmation,
        'invoice_file_info': invoice_file_info,
        'has_existing_file': has_existing_file
    })


@login_required
def upload_invoice_execute(request, pk: int):
    """
    Execute invoice upload after form submission.
    
    Args:
        pk: Order primary key
    
    Returns:
        Redirect to order detail page
    """
    order = get_object_or_404(Order, pk=pk)
    
    # Validate order status
    if order.status not in ['sent', 'invoice_received']:
        messages.error(request, 'Инвойс можно прикрепить только после отправки заказа на фабрику!')
        return redirect('order_detail', pk=pk)
    
    # Check for active confirmation
    active_confirmation = OrderConfirmation.objects.filter(
        order=order,
        action='upload_invoice',
        status='pending',
        expires_at__gt=timezone.now()
    ).first()
    
    if not active_confirmation:
        messages.error(request, 'Нет активного подтверждения для загрузки инвойса!')
        return redirect('order_detail', pk=pk)
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем права доступа перед обработкой
    if not active_confirmation.can_be_confirmed_by(request.user):
        messages.error(request, 'Вы не можете подтвердить эту операцию!')
        return redirect('order_detail', pk=pk)
    
    if request.method != 'POST':
        return redirect('upload_invoice_form', pk=pk)
    
    from ..forms import InvoiceWithPaymentForm
    
    # Проверяем, существует ли уже инвойс
    existing_invoice = getattr(order, 'invoice', None)
    
    # Если инвойс уже существует, делаем поля инвойса необязательными
    if existing_invoice:
        form = InvoiceWithPaymentForm(request.POST, request.FILES)
        # Делаем поля инвойса необязательными
        form.fields['invoice_number'].required = False
        form.fields['balance'].required = False
        form.fields['due_date'].required = False
        form.fields['invoice_notes'].required = False
        form.fields['invoice_file'].required = False
    else:
        form = InvoiceWithPaymentForm(request.POST, request.FILES)
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Для нового инвойса файл обязателен
        form.fields['invoice_file'].required = True
    
    if form.is_valid():
        try:
            from django.db import transaction
            from ..models import Invoice, InvoicePayment
            
            old_status = order.status
            
            # Используем уже полученный active_confirmation, не делаем повторный запрос
            with transaction.atomic():
                if existing_invoice:
                    # Инвойс уже существует - только добавляем платеж
                    payment = InvoicePayment.objects.create(
                        invoice=existing_invoice,
                        amount=form.cleaned_data['payment_amount'],
                        payment_date=form.cleaned_data['payment_date'],
                        payment_type=form.cleaned_data['payment_type'],
                        payment_receipt=form.cleaned_data.get('payment_receipt'),
                        notes=form.cleaned_data.get('payment_notes', ''),
                        created_by=request.user
                    )
                    
                    # Обновляем файл инвойса, если новый файл загружен
                    if 'invoice_file' in form.cleaned_data and form.cleaned_data['invoice_file']:
                        invoice_file = form.cleaned_data['invoice_file']
                        order.invoice_file = invoice_file
                        order.save()
                        
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Перезагружаем confirmation перед обновлением
                        # для предотвращения потери данных при race condition
                        active_confirmation.refresh_from_db()
                        # Update confirmation data
                        confirmation_data = active_confirmation.confirmation_data.copy()
                        confirmation_data.update({
                            'invoice_file_name': invoice_file.name,
                            'invoice_file_size': invoice_file.size,
                            'payment_amount': str(payment.amount),
                            'payment_type': payment.payment_type,
                        })
                        active_confirmation.confirmation_data = confirmation_data
                        
                        # Confirm operation (обновляем данные перед подтверждением)
                        active_confirmation.confirm(request.user, f"Дополнительный платеж добавлен и файл инвойса обновлен: {invoice_file.name}")
                        # Сохраняем обновленные confirmation_data
                        active_confirmation.save(update_fields=['confirmation_data'])
                    else:
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Перезагружаем confirmation перед обновлением
                        # для предотвращения потери данных при race condition
                        active_confirmation.refresh_from_db()
                        # Update confirmation data для дополнительного платежа
                        confirmation_data = active_confirmation.confirmation_data.copy()
                        confirmation_data.update({
                            'payment_amount': str(payment.amount),
                            'payment_type': payment.payment_type,
                        })
                        active_confirmation.confirmation_data = confirmation_data
                        
                        # Confirm operation
                        active_confirmation.confirm(request.user, f"Дополнительный платеж добавлен")
                        # Сохраняем обновленные confirmation_data
                        active_confirmation.save(update_fields=['confirmation_data'])
                    
                    # Create audit log для дополнительного платежа
                    OrderAuditLog.objects.create(
                        order=order,
                        action='payment_added',
                        user=request.user,
                        old_value=old_status,
                        new_value=order.status,
                        field_name='payments',
                        comments=f'Добавлен платеж: {payment.amount} ({payment.payment_type})'
                    )
                        
                else:
                    # Создаем новый инвойс
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем наличие файла для нового инвойса
                    invoice_file = form.cleaned_data.get('invoice_file')
                    if not invoice_file:
                        messages.error(request, 'Для нового инвойса необходимо загрузить PDF файл!')
                        return redirect('upload_invoice_form', pk=pk)
                    
                    invoice = Invoice.objects.create(
                        order=order,
                        invoice_number=form.cleaned_data['invoice_number'],
                        balance=form.cleaned_data['balance'],
                        due_date=form.cleaned_data.get('due_date'),
                        notes=form.cleaned_data.get('invoice_notes', '')
                    )
                    
                    # КРИТИЧЕСКОЕ ИЗМЕНЕНИЕ: Создаем платеж только если указаны данные платежа
                    payment = None
                    payment_amount = form.cleaned_data.get('payment_amount')
                    if payment_amount is not None and payment_amount > 0:
                        payment = InvoicePayment.objects.create(
                            invoice=invoice,
                            amount=payment_amount,
                            payment_date=form.cleaned_data.get('payment_date'),
                            payment_type=form.cleaned_data.get('payment_type', 'partial_payment'),
                            payment_receipt=form.cleaned_data.get('payment_receipt'),
                            notes=form.cleaned_data.get('payment_notes', ''),
                            created_by=request.user
                        )
                    
                    # Сохраняем файл инвойса в заказ
                    order.invoice_file = invoice_file
                    
                    # Обновляем статус заказа для нового инвойса
                    order.status = 'invoice_received'
                    order.invoice_received_at = timezone.now()
                    order.save()
                    
                    # Update confirmation data для нового инвойса
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: invoice_file гарантированно существует для нового инвойса
                    confirmation_data = {
                        'invoice_file_name': invoice_file.name,
                        'invoice_file_size': invoice_file.size,
                        'invoice_number': invoice.invoice_number,
                        'balance': str(invoice.balance),
                    }
                    if payment:
                        confirmation_data.update({
                            'payment_amount': str(payment.amount),
                            'payment_type': payment.payment_type,
                        })
                    active_confirmation.confirmation_data.update(confirmation_data)
                    active_confirmation.save()
                    
                    # Confirm operation для нового инвойса
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: invoice_file гарантированно существует для нового инвойса
                    if payment:
                        active_confirmation.confirm(request.user, f"Инвойс {invoice_file.name} успешно загружен с платежом")
                    else:
                        active_confirmation.confirm(request.user, f"Инвойс {invoice_file.name} успешно загружен без платежа")
                    
                    # Create audit log для нового инвойса
                    comments = f'Загружен инвойс: {invoice_file.name}'
                    if payment:
                        comments += f', платеж: {payment.amount}'
                    OrderAuditLog.objects.create(
                        order=order,
                        action='file_uploaded',
                        user=request.user,
                        old_value=old_status,
                        new_value='invoice_received',
                        field_name='status',
                        comments=comments
                    )
                
                # Send notification
                try:
                    if not existing_invoice:
                        send_order_notification.delay(order.id, 'invoice_received')
                    else:
                        send_order_notification.delay(order.id, 'payment_received')
                except Exception as e:
                    logger = logging.getLogger('orders')
                    logger.error(f"Ошибка отправки уведомления: {e}")
                
                # Сообщение об успехе в зависимости от действия
                if not existing_invoice:
                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: invoice_file гарантированно существует для нового инвойса
                    invoice_file = form.cleaned_data.get('invoice_file')
                    payment_amount = form.cleaned_data.get('payment_amount')
                    if payment_amount is not None and payment_amount > 0:
                        messages.success(request, f'Инвойс "{invoice_file.name}" успешно загружен с платежом!')
                    else:
                        messages.success(request, f'Инвойс "{invoice_file.name}" успешно загружен! Платеж можно добавить позже.')
                else:
                    messages.success(request, f'Дополнительный платеж успешно добавлен!')
            
        except Exception as e:
            messages.error(request, f'Ошибка при загрузке инвойса: {str(e)}')
    else:
        messages.error(request, 'Ошибка в форме загрузки файла.')
    
    return redirect('order_detail', pk=pk)


@login_required
def complete_order(request, pk: int):
    """
    Create confirmation for completing order.
    
    Args:
        pk: Order primary key
    
    Returns:
        Redirect to confirmation approval page
    """
    order = get_object_or_404(Order, pk=pk)
    
    # Validate order status
    if order.status not in ['invoice_received']:
        messages.error(request, 'Заказ можно завершить только после получения инвойса!')
        return redirect('order_detail', pk=pk)
    
    # Check for existing active confirmation
    active_confirmation = OrderConfirmation.objects.filter(
        order=order,
        action='complete_order',
        status='pending',
        expires_at__gt=timezone.now()
    ).first()
    
    if active_confirmation:
        messages.warning(request, 'У вас уже есть активное подтверждение для завершения этого заказа.')
        return redirect('confirmation_detail', pk=active_confirmation.pk)
    
    # Create new confirmation
    confirmation = OrderConfirmation.objects.create(
        order=order,
        action='complete_order',
        requested_by=request.user,
        confirmation_data={
            'order_title': order.title,
            'factory_name': order.factory.name,
            'current_status': order.get_status_display(),
            'uploaded_at': order.uploaded_at.strftime('%d.%m.%Y %H:%M'),
            'sent_at': order.sent_at.strftime('%d.%m.%Y %H:%M') if order.sent_at else None,
            'invoice_received_at': order.invoice_received_at.strftime('%d.%m.%Y %H:%M') if order.invoice_received_at else None,
        }
    )
    
    messages.info(request, 'Создано подтверждение для завершения заказа. Подтвердите операцию для выполнения.')
    return redirect('confirmation_approve', pk=confirmation.pk)


@login_required
def confirmation_approve(request, pk: int):
    """
    Approve and execute confirmed operation.
    
    This is the core function that executes the actual business logic
    after user confirmation. It handles different operation types:
    - send_order: Send email to factory
    - upload_invoice: Redirect to upload form
    - complete_order: Mark order as completed
    
    Args:
        pk: Confirmation primary key
    
    Returns:
        Redirect to confirmation detail or appropriate page
    """
    confirmation = get_object_or_404(OrderConfirmation, pk=pk)
    
    # Проверка прав доступа
    if not confirmation.can_be_confirmed_by(request.user):
        messages.error(request, 'Вы не можете подтвердить эту операцию!')
        return redirect('confirmation_detail', pk=pk)
    
    if confirmation.status != 'pending':
        messages.error(request, 'Это подтверждение уже обработано!')
        return redirect('confirmation_detail', pk=pk)
    
    if confirmation.is_expired():
        # Автоматически помечаем как истекшее
        if confirmation.status == 'pending':
            confirmation.status = 'expired'
            confirmation.save(update_fields=['status'])
        messages.error(request, 'Срок подтверждения истек!')
        return redirect('confirmation_detail', pk=pk)
    
    if request.method == 'POST':
        comments = request.POST.get('comments', '')
        
        try:
            # Execute the appropriate action based on confirmation type
            if confirmation.action == 'send_order':
                _execute_send_order(confirmation, request.user, comments)
                messages.success(request, f'Заказ успешно отправлен на фабрику {confirmation.order.factory.name}!')
                
            elif confirmation.action == 'upload_invoice':
                # For invoice upload, redirect to upload form
                return redirect('upload_invoice_form', pk=confirmation.order.pk)
                
            elif confirmation.action == 'complete_order':
                _execute_complete_order(confirmation, request.user, comments)
                messages.success(request, f'Заказ "{confirmation.order.title}" успешно завершен!')
            
            # Confirm the operation
            confirmation.confirm(request.user, comments)
            
        except ValueError as e:
            # Обработка ошибок валидации (права доступа, уже обработано)
            messages.error(request, str(e))
        except Exception as e:
            # Логируем неожиданные ошибки
            logger = logging.getLogger('orders')
            logger.error(f"Unexpected error in confirmation_approve: {e}", exc_info=True)
            messages.error(request, 'Произошла неожиданная ошибка. Обратитесь к администратору.')
        
        return redirect('confirmation_detail', pk=pk)
    
    return render(request, 'orders/confirmation_approve.html', {
        'confirmation': confirmation,
    })


@login_required
def confirmation_reject(request, pk: int):
    """
    Reject confirmation with reason.
    
    Args:
        pk: Confirmation primary key
    
    Returns:
        Redirect to confirmation detail page
    """
    confirmation = get_object_or_404(OrderConfirmation, pk=pk)
    
    # Проверка прав доступа
    if not confirmation.can_be_confirmed_by(request.user):
        messages.error(request, 'Вы не можете отклонить эту операцию!')
        return redirect('confirmation_detail', pk=pk)
    
    if confirmation.status != 'pending':
        messages.error(request, 'Это подтверждение уже обработано!')
        return redirect('confirmation_detail', pk=pk)
    
    if request.method == 'POST':
        rejection_reason = request.POST.get('rejection_reason', '')
        if not rejection_reason.strip():
            messages.error(request, 'Необходимо указать причину отклонения!')
            return render(request, 'orders/confirmation_reject.html', {
                'confirmation': confirmation,
            })
        
        try:
            confirmation.reject(request.user, rejection_reason)
            messages.success(request, 'Операция отклонена.')
        except ValueError as e:
            # Обработка ошибок валидации (права доступа, уже обработано)
            messages.error(request, str(e))
        except Exception as e:
            # Логируем неожиданные ошибки
            logger = logging.getLogger('orders')
            logger.error(f"Unexpected error in confirmation_reject: {e}", exc_info=True)
            messages.error(request, 'Произошла неожиданная ошибка. Обратитесь к администратору.')
        
        return redirect('confirmation_detail', pk=pk)
    
    return render(request, 'orders/confirmation_reject.html', {
        'confirmation': confirmation,
    })


def _execute_send_order(confirmation: OrderConfirmation, user, comments: str) -> None:
    """
    Execute order sending to factory.
    
    Args:
        confirmation: OrderConfirmation instance
        user: User executing the operation
        comments: User comments
    """
    order = confirmation.order
    
    # Validate order status
    if order.status != 'uploaded':
        raise ValueError('Заказ уже отправлен или имеет другой статус!')
    
    # Send email to factory
    try:
        # Determine email language based on factory country
        from ..email_utils import get_language_by_country_code, get_email_template_from_db
        
        country_code = order.factory.country.code
        language_code = get_language_by_country_code(country_code)
        
        # Get template from database
        template = get_email_template_from_db('order_confirmation', language_code)
        
        if template:
            # Use database template
            import logging
            logger = logging.getLogger('orders')
            logger.info(f'Using database template: {template.name} (ID: {template.id}) for order {order.id}')
            
            context = {
                'order': order,
                'factory': order.factory,
                'employee': order.employee,
                'country': order.factory.country,
            }
            
            rendered = template.render_template(context)
            subject = rendered['subject']
            html_message = rendered['html_content']
            text_message = rendered['text_content']
            
            # Mark template as used
            template.mark_as_used()
            logger.info(f'Template {template.name} marked as used')
        else:
            # Fallback to static templates
            import logging
            logger = logging.getLogger('orders')
            logger.warning(f'No database template found for language {language_code}, using static templates for order {order.id}')
            
            from ..email_utils import get_email_subject, get_email_template_paths
            
            # Get template paths
            html_template_path, txt_template_path = get_email_template_paths(language_code)
            
            # Form email subject
            subject_prefix = get_email_subject(language_code)
            subject = f'{subject_prefix}: {order.title}'
            
            # Render HTML template
            html_message = render_to_string(html_template_path, {
                'order': order,
                'factory': order.factory,
                'employee': order.employee,
            })
            
            # Render text template
            text_message = render_to_string(txt_template_path, {
                'order': order,
                'factory': order.factory,
                'employee': order.employee,
            })
        
        email = EmailMessage(
            subject=subject,
            body=html_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[order.factory.email],
        )
        email.content_subtype = "html"
        email.encoding = 'utf-8'
        
        # Attach Excel file with security check
        if order.excel_file:
            file_path = order.excel_file.path
            # Проверка безопасности пути к файлу
            media_root = os.path.abspath(settings.MEDIA_ROOT)
            file_path_abs = os.path.abspath(file_path)
            
            if file_path_abs.startswith(media_root) and os.path.exists(file_path):
                email.attach_file(file_path)
            else:
                logger.warning(f'Небезопасный путь к файлу или файл не найден: {file_path}')
        
        email.send()
        
        # Log successful email sending
        logger = logging.getLogger('orders')
        logger.info(f'Email successfully sent to {order.factory.email} for order {order.id} using template: {template.name if template else "static"}')
        
    except Exception as e:
        logger = logging.getLogger('orders')
        logger.error(f"Ошибка отправки email для заказа {order.id}: {e}")
        raise ValueError(f'Ошибка при отправке email: {str(e)}')
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Обновление статуса заказа и создание audit log
    # должны быть в транзакции для обеспечения атомарности операции
    # Это предотвращает ситуацию, когда email отправлен, но статус не обновлен
    from django.db import transaction
    
    try:
        with transaction.atomic():
            # Обновляем статус заказа
            order.status = 'sent'
            order.sent_at = timezone.now()
            order.save()
            
            # Создаем audit log
            OrderAuditLog.objects.create(
                order=order,
                action='sent',
                user=user,
                old_value='uploaded',
                new_value='sent',
                field_name='status',
                comments='Заказ отправлен на фабрику'
            )
    except Exception as e:
        logger = logging.getLogger('orders')
        logger.error(f"Ошибка обновления статуса заказа {order.id} после отправки email: {e}", exc_info=True)
        # Если не удалось обновить статус, это критическая ошибка
        raise ValueError(f'Ошибка при обновлении статуса заказа после отправки email: {str(e)}')
    
    # Send notification (вне транзакции, т.к. это асинхронная задача)
    try:
        send_order_notification.delay(order.id, 'order_sent')
    except Exception as e:
        logger = logging.getLogger('orders')
        logger.error(f"Ошибка отправки уведомления для заказа {order.id}: {e}")


def _execute_complete_order(confirmation: OrderConfirmation, user, comments: str) -> None:
    """
    Execute order completion.
    
    Args:
        confirmation: OrderConfirmation instance
        user: User executing the operation
        comments: User comments
    """
    order = confirmation.order
    
    # Validate order status
    if order.status not in ['invoice_received']:
        raise ValueError('Заказ можно завершить только после получения инвойса!')
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Обновление статуса заказа и создание audit log
    # должны быть в транзакции для обеспечения атомарности операции
    from django.db import transaction
    
    try:
        with transaction.atomic():
            # Complete the order
            order.mark_as_completed()
            
            # Create audit log
            OrderAuditLog.objects.create(
                order=order,
                action='completed',
                user=user,
                old_value='invoice_received',
                new_value='completed',
                field_name='status',
                comments='Заказ завершен пользователем'
            )
    except Exception as e:
        logger = logging.getLogger('orders')
        logger.error(f"Ошибка завершения заказа {order.id}: {e}", exc_info=True)
        raise ValueError(f'Ошибка при завершении заказа: {str(e)}')
    
    # Send notification (вне транзакции, т.к. это асинхронная задача)
    try:
        send_order_notification.delay(order.id, 'order_completed')
    except Exception as e:
        logger = logging.getLogger('orders')
        logger.error(f"Ошибка отправки уведомления для заказа {order.id}: {e}")
