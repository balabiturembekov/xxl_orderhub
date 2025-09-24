"""
Views для управления платежами по инвойсам.

Содержит функциональность для:
- Создания инвойсов с первым платежом
- Добавления дополнительных платежей
- Просмотра истории платежей
- Управления статусами платежей
"""

from typing import Dict, Any, Optional
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse, Http404
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from django.urls import reverse_lazy, reverse
from django.db import transaction
from django.utils import timezone
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count, Avg
from django.utils.translation import gettext as _

from ..models import Order, Invoice, InvoicePayment, OrderAuditLog
from ..forms import InvoiceForm, InvoicePaymentForm, InvoiceWithPaymentForm


@login_required
def upload_invoice_with_payment(request, order_id):
    """
    Обработка загрузки инвойса с первым платежом.
    
    Создает инвойс и первый платеж одновременно.
    """
    order = get_object_or_404(Order, id=order_id, employee=request.user)
    
    # Проверяем, что у заказа еще нет инвойса
    if hasattr(order, 'invoice'):
        messages.error(request, _('У этого заказа уже есть инвойс.'))
        return redirect('order_detail', order_id=order.id)
    
    if request.method == 'POST':
        form = InvoiceWithPaymentForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Создаем инвойс
                    invoice = Invoice.objects.create(
                        order=order,
                        invoice_number=form.cleaned_data['invoice_number'],
                        balance=form.cleaned_data['balance'],
                        due_date=form.cleaned_data.get('due_date'),
                        notes=form.cleaned_data.get('invoice_notes', '')
                    )
                    
                    # Создаем первый платеж
                    payment = InvoicePayment.objects.create(
                        invoice=invoice,
                        amount=form.cleaned_data['payment_amount'],
                        payment_date=form.cleaned_data['payment_date'],
                        payment_type=form.cleaned_data['payment_type'],
                        payment_receipt=form.cleaned_data['payment_receipt'],
                        notes=form.cleaned_data.get('payment_notes', ''),
                        created_by=request.user
                    )
                    
                    # Обновляем статус заказа
                    order.status = 'invoice_received'
                    order.invoice_received_at = timezone.now()
                    order.save()
                    
                    # Создаем запись аудита
                    OrderAuditLog.log_action(
                        order=order,
                        user=request.user,
                        action='file_uploaded',
                        field_name='invoice_file',
                        new_value=f'Инвойс {invoice.invoice_number} с платежом {payment.amount}',
                        comments=f'Загружен инвойс с первым платежом. Тип: {payment.get_payment_type_display()}'
                    )
                    
                    messages.success(
                        request, 
                        _('Инвойс успешно загружен с первым платежом! '
                          'Номер инвойса: {invoice_number}, '
                          'Сумма платежа: {amount}').format(
                            invoice_number=invoice.invoice_number,
                            amount=payment.amount
                        )
                    )
                    
                    return redirect('order_detail', order_id=order.id)
                    
            except Exception as e:
                messages.error(request, _('Ошибка при создании инвойса: {error}').format(error=str(e)))
        else:
            messages.error(request, _('Пожалуйста, исправьте ошибки в форме.'))
    else:
        form = InvoiceWithPaymentForm()
    
    context = {
        'order': order,
        'form': form,
        'title': _('Загрузка инвойса с платежом')
    }
    
    return render(request, 'orders/upload_invoice_form.html', context)


@method_decorator(login_required, name='dispatch')
class InvoiceDetailView(DetailView):
    """
    Детальный просмотр инвойса с историей платежей.
    """
    model = Invoice
    template_name = 'orders/invoice_detail.html'
    context_object_name = 'invoice'
    
    def get_queryset(self):
        """Фильтруем инвойсы по пользователю"""
        return Invoice.objects.filter(order__employee=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_object()
        
        # Получаем историю платежей
        payments = invoice.payments.all().order_by('-payment_date', '-created_at')
        
        # Пагинация платежей
        paginator = Paginator(payments, 10)
        page_number = self.request.GET.get('page')
        payments_page = paginator.get_page(page_number)
        
        context.update({
            'payments': payments_page,
            'total_payments': payments.count(),
            'payment_progress': invoice.payment_progress_percentage,
            'is_overdue': invoice.is_overdue,
            'order': invoice.order,
        })
        
        return context


@method_decorator(login_required, name='dispatch')
class PaymentCreateView(CreateView):
    """
    Создание нового платежа по инвойсу.
    """
    model = InvoicePayment
    form_class = InvoicePaymentForm
    template_name = 'orders/payment_form.html'
    
    def get_invoice(self):
        """Получаем инвойс из URL"""
        invoice_id = self.kwargs.get('invoice_id')
        return get_object_or_404(
            Invoice, 
            id=invoice_id, 
            order__employee=self.request.user
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['invoice'] = self.get_invoice()
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invoice'] = self.get_invoice()
        context['title'] = _('Добавить платеж')
        return context
    
    def form_valid(self, form):
        invoice = self.get_invoice()
        
        # Проверяем, что сумма платежа не превышает остаток
        if form.cleaned_data['amount'] > invoice.remaining_amount:
            form.add_error('amount', _('Сумма платежа не может превышать остаток к доплате.'))
            return self.form_invalid(form)
        
        # Сохраняем платеж
        payment = form.save(commit=False)
        payment.invoice = invoice
        payment.created_by = self.request.user
        payment.save()
        
        # Создаем запись аудита
        OrderAuditLog.log_action(
            order=invoice.order,
            user=self.request.user,
            action='updated',
            field_name='payment',
            new_value=f'Добавлен платеж {payment.amount} ({payment.get_payment_type_display()})',
            comments=f'Тип платежа: {payment.get_payment_type_display()}, Дата: {payment.payment_date}'
        )
        
        messages.success(
            self.request,
            _('Платеж успешно добавлен! Сумма: {amount}, Тип: {type}').format(
                amount=payment.amount,
                type=payment.get_payment_type_display()
            )
        )
        
        return redirect('invoice_detail', pk=invoice.id)


@method_decorator(login_required, name='dispatch')
class PaymentUpdateView(UpdateView):
    """
    Редактирование существующего платежа.
    """
    model = InvoicePayment
    form_class = InvoicePaymentForm
    template_name = 'orders/payment_form.html'
    
    def get_queryset(self):
        """Фильтруем платежи по пользователю"""
        return InvoicePayment.objects.filter(
            invoice__order__employee=self.request.user
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['invoice'] = self.get_object().invoice
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invoice'] = self.get_object().invoice
        context['title'] = _('Редактировать платеж')
        return context
    
    def form_valid(self, form):
        payment = self.get_object()
        old_amount = payment.amount
        
        # Сохраняем изменения
        payment = form.save()
        
        # Создаем запись аудита
        OrderAuditLog.log_action(
            order=payment.invoice.order,
            user=self.request.user,
            action='updated',
            field_name='payment',
            old_value=f'Платеж {old_amount}',
            new_value=f'Платеж {payment.amount}',
            comments=f'Изменен платеж. Старая сумма: {old_amount}, Новая сумма: {payment.amount}'
        )
        
        messages.success(
            self.request,
            _('Платеж успешно обновлен!')
        )
        
        return redirect('invoice_detail', pk=payment.invoice.id)


@login_required
@require_http_methods(["POST"])
def delete_payment(request, payment_id):
    """
    Удаление платежа по инвойсу.
    """
    payment = get_object_or_404(
        InvoicePayment,
        id=payment_id,
        invoice__order__employee=request.user
    )
    
    invoice = payment.invoice
    amount = payment.amount
    
    try:
        with transaction.atomic():
            # Создаем запись аудита перед удалением
            OrderAuditLog.log_action(
                order=invoice.order,
                user=request.user,
                action='updated',
                field_name='payment',
                old_value=f'Платеж {amount}',
                new_value='Платеж удален',
                comments=f'Удален платеж на сумму {amount}'
            )
            
            # Удаляем платеж
            payment.delete()
            
            messages.success(
                request,
                _('Платеж успешно удален! Сумма: {amount}').format(amount=amount)
            )
            
    except Exception as e:
        messages.error(request, _('Ошибка при удалении платежа: {error}').format(error=str(e)))
    
    return redirect('invoice_detail', pk=invoice.id)


@method_decorator(login_required, name='dispatch')
class InvoiceListView(ListView):
    """
    Список всех инвойсов пользователя с фильтрацией.
    """
    model = Invoice
    template_name = 'orders/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    
    def get_queryset(self):
        """Фильтруем инвойсы по пользователю и статусу"""
        queryset = Invoice.objects.filter(
            order__employee=self.request.user
        ).select_related('order', 'order__factory').prefetch_related('payments')
        
        # Фильтрация по статусу
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
        
        # Фильтрация по просрочке
        overdue = self.request.GET.get('overdue')
        if overdue == 'true':
            queryset = queryset.filter(
                due_date__lt=timezone.now().date(),
                status__in=['pending', 'partial']
            )
        
        # Поиск по номеру инвойса
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(invoice_number__icontains=search) |
                Q(order__title__icontains=search) |
                Q(order__factory__name__icontains=search)
            )
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Статистика
        queryset = self.get_queryset()
        context.update({
            'total_invoices': queryset.count(),
            'pending_invoices': queryset.filter(status='pending').count(),
            'partial_invoices': queryset.filter(status='partial').count(),
            'paid_invoices': queryset.filter(status='paid').count(),
            'overdue_invoices': queryset.filter(
                due_date__lt=timezone.now().date(),
                status__in=['pending', 'partial']
            ).count(),
            'total_amount': queryset.aggregate(Sum('balance'))['balance__sum'] or 0,
            'total_paid': queryset.aggregate(Sum('total_paid'))['total_paid__sum'] or 0,
        })
        
        return context


@login_required
def payment_analytics(request):
    """
    Аналитика по платежам пользователя.
    """
    user_invoices = Invoice.objects.filter(order__employee=request.user)
    
    # Общая статистика
    total_invoices = user_invoices.count()
    total_amount = user_invoices.aggregate(Sum('balance'))['balance__sum'] or 0
    total_paid = user_invoices.aggregate(Sum('total_paid'))['total_paid__sum'] or 0
    remaining_amount = total_amount - total_paid
    
    # Статистика по статусам
    status_stats = user_invoices.values('status').annotate(
        count=Count('id'),
        total_balance=Sum('balance'),
        total_paid=Sum('total_paid')
    )
    
    # Статистика по типам платежей
    payment_stats = InvoicePayment.objects.filter(
        invoice__order__employee=request.user
    ).values('payment_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    )
    
    # Просроченные инвойсы
    overdue_invoices = user_invoices.filter(
        due_date__lt=timezone.now().date(),
        status__in=['pending', 'partial']
    )
    
    context = {
        'total_invoices': total_invoices,
        'total_amount': total_amount,
        'total_paid': total_paid,
        'remaining_amount': remaining_amount,
        'status_stats': status_stats,
        'payment_stats': payment_stats,
        'overdue_invoices': overdue_invoices,
        'payment_progress': (total_paid / total_amount * 100) if total_amount > 0 else 0,
    }
    
    return render(request, 'orders/payment_analytics.html', context)
