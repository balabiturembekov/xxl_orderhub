"""
Order confirmation system views.

This module handles the critical operations confirmation system:
- Creating confirmations for critical operations
- Approving/rejecting confirmations
- Managing confirmation workflow
- Audit logging for all operations
"""

from typing import Dict, Any
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
            order__employee=self.request.user
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
    confirmation = get_object_or_404(OrderConfirmation, pk=pk, order__employee=request.user)
    
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
    order = get_object_or_404(Order, pk=pk, employee=request.user)
    
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
    order = get_object_or_404(Order, pk=pk, employee=request.user)
    
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
    order = get_object_or_404(Order, pk=pk, employee=request.user)
    
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
    
    form = InvoiceUploadForm()
    return render(request, 'orders/upload_invoice_form.html', {
        'form': form,
        'order': order,
        'confirmation': active_confirmation
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
    order = get_object_or_404(Order, pk=pk, employee=request.user)
    
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
    
    if request.method != 'POST':
        return redirect('upload_invoice_form', pk=pk)
    
    form = InvoiceUploadForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            invoice_file = form.cleaned_data['invoice_file']
            old_status = order.status
            
            # Update confirmation data
            active_confirmation.confirmation_data.update({
                'invoice_file_name': invoice_file.name,
                'invoice_file_size': invoice_file.size,
            })
            active_confirmation.save()
            
            # Update order status
            order.mark_invoice_received(invoice_file)
            
            # Confirm operation
            active_confirmation.confirm(request.user, f"Инвойс {invoice_file.name} успешно загружен")
            
            # Create audit log
            OrderAuditLog.objects.create(
                order=order,
                action='file_uploaded',
                user=request.user,
                old_value=old_status,
                new_value='invoice_received',
                field_name='status',
                comments=f'Загружен инвойс: {invoice_file.name}'
            )
            
            # Send notification
            try:
                send_order_notification.delay(order.id, 'invoice_received')
            except Exception as e:
                print(f"Ошибка отправки уведомления: {e}")
            
            messages.success(request, f'Инвойс "{invoice_file.name}" успешно загружен!')
            
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
    order = get_object_or_404(Order, pk=pk, employee=request.user)
    
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
    confirmation = get_object_or_404(OrderConfirmation, pk=pk, order__employee=request.user)
    
    if confirmation.status != 'pending':
        messages.error(request, 'Это подтверждение уже обработано!')
        return redirect('confirmation_detail', pk=pk)
    
    if confirmation.is_expired():
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
            
        except Exception as e:
            messages.error(request, f'Ошибка при подтверждении: {str(e)}')
        
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
    confirmation = get_object_or_404(OrderConfirmation, pk=pk, order__employee=request.user)
    
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
        except Exception as e:
            messages.error(request, f'Ошибка при отклонении: {str(e)}')
        
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
        from ..email_utils import get_language_by_country_code, get_email_subject, get_email_template_paths
        
        country_code = order.factory.country.code
        language_code = get_language_by_country_code(country_code)
        
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
        
        # Attach Excel file
        if order.excel_file:
            email.attach_file(order.excel_file.path)
        
        email.send()
        
    except Exception as e:
        print(f"Ошибка отправки email: {e}")
        raise ValueError(f'Ошибка при отправке email: {str(e)}')
    
    # Update order status
    order.status = 'sent'
    order.sent_at = timezone.now()
    order.save()
    
    # Create audit log
    OrderAuditLog.objects.create(
        order=order,
        action='sent',
        user=user,
        old_value='uploaded',
        new_value='sent',
        field_name='status',
        comments='Заказ отправлен на фабрику'
    )
    
    # Send notification
    try:
        send_order_notification.delay(order.id, 'order_sent')
    except Exception as e:
        print(f"Ошибка отправки уведомления: {e}")


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
    
    # Send notification
    try:
        send_order_notification.delay(order.id, 'order_completed')
    except Exception as e:
        print(f"Ошибка отправки уведомления: {e}")
