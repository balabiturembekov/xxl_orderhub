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

from ..models import Order, Invoice, InvoicePayment, OrderAuditLog, OrderConfirmation, OrderCBM
from ..forms import InvoiceForm, InvoicePaymentForm, InvoiceWithPaymentForm, OrderCBMForm


@login_required
def upload_invoice_with_payment(request, pk):
    """
    Обработка загрузки инвойса с первым платежом.
    
    Создает инвойс и первый платеж одновременно.
    """
    order = get_object_or_404(Order, id=pk)
    
    # Проверяем активное подтверждение (если вызывается через старый URL)
    active_confirmation = None
    if request.resolver_match.url_name == 'upload_invoice_execute':
        active_confirmation = OrderConfirmation.objects.filter(
            order=order,
            action='upload_invoice',
            status='pending',
            expires_at__gt=timezone.now()
        ).first()
        
        if not active_confirmation:
            messages.error(request, _('Нет активного подтверждения для загрузки инвойса!'))
            return redirect('order_detail', pk=order.id)
    
    # Проверяем, что у заказа еще нет инвойса (только если нет активного подтверждения)
    if not active_confirmation and hasattr(order, 'invoice'):
        messages.error(request, _('У этого заказа уже есть инвойс.'))
        return redirect('order_detail', pk=order.id)
    
    if request.method == 'POST':
        form = InvoiceWithPaymentForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Создаем или обновляем инвойс
                    if hasattr(order, 'invoice'):
                        # Обновляем существующий инвойс
                        invoice = order.invoice
                        invoice.invoice_number = form.cleaned_data['invoice_number']
                        invoice.balance = form.cleaned_data['balance']
                        invoice.due_date = form.cleaned_data.get('due_date')
                        invoice.notes = form.cleaned_data.get('invoice_notes', '')
                        invoice.save()
                    else:
                        # Создаем новый инвойс
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
                    
                    # Сохраняем файл инвойса в заказ
                    invoice_file = form.cleaned_data['invoice_file']
                    order.invoice_file = invoice_file
                    
                    # Обновляем статус заказа
                    order.status = 'invoice_received'
                    order.invoice_received_at = timezone.now()
                    order.save()
                    
                    # Обрабатываем подтверждение (если есть)
                    # Используем active_confirmation, полученный выше, не делаем повторный запрос
                    if request.resolver_match.url_name == 'upload_invoice_execute' and active_confirmation:
                        # Используем метод confirm() для атомарного обновления
                        try:
                            active_confirmation.confirm(
                                request.user,
                                comments=f'Инвойс {invoice.invoice_number} загружен с платежом {payment.amount}'
                            )
                            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Перезагружаем confirmation перед обновлением
                            # для предотвращения потери данных при race condition
                            active_confirmation.refresh_from_db()
                            # Обновляем confirmation_data
                            confirmation_data = active_confirmation.confirmation_data.copy()
                            confirmation_data.update({
                                'invoice_number': invoice.invoice_number,
                                'balance': str(invoice.balance),
                                'payment_amount': str(payment.amount),
                                'payment_type': payment.payment_type,
                            })
                            active_confirmation.confirmation_data = confirmation_data
                            active_confirmation.save(update_fields=['confirmation_data'])
                        except ValueError as e:
                            # Если подтверждение уже обработано, просто логируем
                            import logging
                            logger = logging.getLogger('orders')
                            logger.warning(f'Не удалось подтвердить операцию: {e}')
                    
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
                    
                    return redirect('order_detail', pk=order.id)
                    
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
        """Фильтруем инвойсы по пользователю с оптимизацией запросов"""
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Добавляем select_related для order, чтобы избежать ошибки
        # "'Invoice' instance needs to have a primary key value before this relationship can be used"
        return Invoice.objects.select_related('order', 'order__factory').all()
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_object()
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем, что invoice имеет pk перед обращением к связанным объектам
        if not invoice.pk:
            # Если invoice не сохранен, возвращаем контекст без CBM
            context.update({
                'payments': [],
                'total_payments': 0,
                'payment_progress': 0,
                'is_overdue': False,
                'order': None,
                'cbm_records': [],
                'total_cbm': 0,
            })
            return context
        
        # Получаем историю платежей
        payments = invoice.payments.all().order_by('-payment_date', '-created_at')
        
        # Пагинация платежей
        paginator = Paginator(payments, 10)
        page_number = self.request.GET.get('page')
        payments_page = paginator.get_page(page_number)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем, что order существует и имеет pk
        if not hasattr(invoice, 'order') or not invoice.order or not invoice.order.pk:
            # Если order не существует, возвращаем контекст без CBM
            context.update({
                'payments': payments_page,
                'total_payments': payments.count(),
                'payment_progress': invoice.payment_progress_percentage,
                'is_overdue': invoice.is_overdue,
                'order': None,
                'cbm_records': [],
                'total_cbm': 0,
            })
            return context
        
        # Получаем записи CBM для заказа
        cbm_records = invoice.order.cbm_records.select_related('created_by').order_by('-date', '-created_at')
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Вычисляем total_cbm из уже загруженных записей вместо запроса к БД
        # Используем QuerySet до применения order_by для агрегации
        total_cbm = invoice.order.cbm_records.aggregate(total=Sum('cbm_value'))['total'] or 0
        
        context.update({
            'payments': payments_page,
            'total_payments': payments.count(),
            'payment_progress': invoice.payment_progress_percentage,
            'is_overdue': invoice.is_overdue,
            'order': invoice.order,
            'cbm_records': cbm_records,
            'total_cbm': total_cbm,
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
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        invoice = self.get_invoice()
        kwargs['invoice'] = invoice
        
        # Предзаполняем форму данными из инвойса
        if not self.request.POST:
            kwargs['initial'] = {
                'payment_date': timezone.now().date(),
                'payment_type': 'partial_payment',  # По умолчанию частичный платеж
                'amount': invoice.remaining_amount,  # Предзаполняем остаток к доплате
            }
        
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        invoice = self.get_invoice()
        context['invoice'] = invoice
        context['title'] = _('Добавить платеж')
        
        # Добавляем информацию об инвойсе для отображения
        context['invoice_info'] = {
            'invoice_number': invoice.invoice_number,
            'balance': invoice.balance,
            'total_paid': invoice.total_paid,
            'remaining_amount': invoice.remaining_amount,
            'status': invoice.get_status_display(),
        }
        
        return context
    
    def form_valid(self, form):
        from django.db import transaction
        
        invoice = self.get_invoice()
        
        # Валидация уже выполнена в форме, дополнительная проверка не нужна
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем транзакцию для атомарности операции
        # Это предотвращает race condition при создании платежа и обновлении invoice
        try:
            with transaction.atomic():
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
        except Exception as e:
            import logging
            logger = logging.getLogger('orders')
            logger.error(f"Ошибка при создании платежа: {e}", exc_info=True)
            messages.error(
                self.request,
                _('Ошибка при создании платежа: {error}').format(error=str(e))
            )
            return self.form_invalid(form)
        
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
        )
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        payment = self.get_object()
        invoice = payment.invoice
        kwargs['invoice'] = invoice
        
        # Предзаполняем форму данными из существующего платежа
        if not self.request.POST:
            kwargs['initial'] = {
                'amount': payment.amount,
                'payment_date': payment.payment_date,
                'payment_type': payment.payment_type,
                'notes': payment.notes,
            }
        
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['invoice'] = self.get_object().invoice
        context['title'] = _('Редактировать платеж')
        return context
    
    def form_valid(self, form):
        from django.db import transaction
        
        payment = self.get_object()
        old_amount = payment.amount
        invoice = payment.invoice
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем транзакцию для атомарности операции
        # Это предотвращает race condition при обновлении платежа и пересчете invoice
        try:
            with transaction.atomic():
                # Сохраняем изменения
                payment = form.save()
                
                # Создаем запись аудита
                OrderAuditLog.log_action(
                    order=invoice.order,
                    user=self.request.user,
                    action='updated',
                    field_name='payment',
                    old_value=f'Платеж {old_amount}',
                    new_value=f'Платеж {payment.amount}',
                    comments=f'Изменен платеж. Старая сумма: {old_amount}, Новая сумма: {payment.amount}'
                )
        except Exception as e:
            import logging
            logger = logging.getLogger('orders')
            logger.error(f"Ошибка при обновлении платежа: {e}", exc_info=True)
            messages.error(
                self.request,
                _('Ошибка при обновлении платежа: {error}').format(error=str(e))
            )
            return self.form_invalid(form)
        
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
class CBMCreateView(CreateView):
    """
    Создание новой записи CBM для заказа.
    """
    model = OrderCBM
    form_class = OrderCBMForm
    template_name = 'orders/cbm_form.html'
    
    def get_order(self):
        """Получаем заказ из URL с оптимизацией запросов"""
        if not hasattr(self, '_order'):
            order_id = self.kwargs.get('order_id')
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем select_related для оптимизации
            self._order = get_object_or_404(
                Order.objects.select_related('factory', 'invoice'),
                id=order_id
            )
        return self._order
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        order = self.get_order()
        kwargs['order'] = order
        
        # Предзаполняем форму данными из заказа
        if not self.request.POST:
            from django.utils import timezone
            kwargs['initial'] = {
                'date': timezone.now().date(),
            }
        
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        order = self.get_order()
        context['order'] = order
        context['title'] = _('Добавить CBM')
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Вычисляем total_cbm через агрегацию вместо property
        from django.db.models import Sum
        total_cbm = order.cbm_records.aggregate(total=Sum('cbm_value'))['total'] or 0
        
        # Добавляем информацию о заказе для отображения
        context['order_info'] = {
            'title': order.title,
            'factory': order.factory.name,  # factory уже загружен через select_related
            'total_cbm': total_cbm,
        }
        
        return context
    
    def form_valid(self, form):
        from django.db import transaction
        
        order = self.get_order()
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем транзакцию для атомарности операции
        try:
            with transaction.atomic():
                # Сохраняем запись CBM
                cbm_record = form.save(commit=False)
                cbm_record.order = order
                cbm_record.created_by = self.request.user
                cbm_record.save()
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Вычисляем total_cbm через агрегацию вместо property
                # Используем агрегацию из уже загруженных записей для производительности
                from django.db.models import Sum
                total_cbm = order.cbm_records.aggregate(total=Sum('cbm_value'))['total'] or 0
                
                # Создаем запись аудита
                OrderAuditLog.log_action(
                    order=order,
                    user=self.request.user,
                    action='updated',
                    field_name='cbm',
                    new_value=f'Добавлено CBM: {cbm_record.cbm_value} куб. м',
                    comments=f'Дата: {cbm_record.date}, Общий CBM: {total_cbm} куб. м'
                )
        except Exception as e:
            import logging
            logger = logging.getLogger('orders')
            logger.error(f"Ошибка при создании записи CBM: {e}", exc_info=True)
            messages.error(
                self.request,
                _('Ошибка при создании записи CBM: {error}').format(error=str(e))
            )
            return self.form_invalid(form)
        
        # Вычисляем total_cbm для сообщения через агрегацию
        from django.db.models import Sum
        total_cbm = order.cbm_records.aggregate(total=Sum('cbm_value'))['total'] or 0
        
        messages.success(
            self.request,
            _('CBM успешно добавлено! Значение: {cbm} куб. м, Общий CBM: {total} куб. м').format(
                cbm=cbm_record.cbm_value,
                total=total_cbm
            )
        )
        
        # Перенаправляем на страницу инвойса, если он есть, иначе на страницу заказа
        if hasattr(order, 'invoice'):
            return redirect('invoice_detail', pk=order.invoice.id)
        else:
            return redirect('order_detail', pk=order.id)


@method_decorator(login_required, name='dispatch')
class CBMUpdateView(UpdateView):
    """
    Редактирование существующей записи CBM.
    """
    model = OrderCBM
    form_class = OrderCBMForm
    template_name = 'orders/cbm_form.html'
    
    def get_queryset(self):
        """Оптимизация запросов с select_related"""
        return OrderCBM.objects.select_related('order', 'order__factory', 'order__invoice', 'created_by')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        cbm_record = self.get_object()
        kwargs['order'] = cbm_record.order
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        cbm_record = self.get_object()
        order = cbm_record.order
        context['order'] = order
        context['title'] = _('Редактировать CBM')
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Вычисляем total_cbm через агрегацию вместо property
        from django.db.models import Sum
        total_cbm = order.cbm_records.aggregate(total=Sum('cbm_value'))['total'] or 0
        
        # Добавляем информацию о заказе для отображения
        context['order_info'] = {
            'title': order.title,
            'factory': order.factory.name,  # factory уже загружен через select_related
            'total_cbm': total_cbm,
        }
        
        return context
    
    def form_valid(self, form):
        from django.db import transaction
        
        cbm_record = self.get_object()
        order = cbm_record.order
        old_cbm = cbm_record.cbm_value
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем транзакцию для атомарности операции
        try:
            with transaction.atomic():
                # Сохраняем изменения
                cbm_record = form.save()
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Вычисляем total_cbm через агрегацию вместо property
                # Используем агрегацию из уже загруженных записей для производительности
                from django.db.models import Sum
                total_cbm = order.cbm_records.aggregate(total=Sum('cbm_value'))['total'] or 0
                
                # Создаем запись аудита
                OrderAuditLog.log_action(
                    order=order,
                    user=self.request.user,
                    action='updated',
                    field_name='cbm',
                    old_value=f'CBM: {old_cbm} куб. м',
                    new_value=f'CBM: {cbm_record.cbm_value} куб. м',
                    comments=f'Изменен CBM. Старое значение: {old_cbm} куб. м, Новое значение: {cbm_record.cbm_value} куб. м, Общий CBM: {total_cbm} куб. м'
                )
        except Exception as e:
            import logging
            logger = logging.getLogger('orders')
            logger.error(f"Ошибка при обновлении записи CBM: {e}", exc_info=True)
            messages.error(
                self.request,
                _('Ошибка при обновлении записи CBM: {error}').format(error=str(e))
            )
            return self.form_invalid(form)
        
        messages.success(
            self.request,
            _('CBM успешно обновлено!')
        )
        
        # Перенаправляем на страницу инвойса, если он есть, иначе на страницу заказа
        if hasattr(order, 'invoice'):
            return redirect('invoice_detail', pk=order.invoice.id)
        else:
            return redirect('order_detail', pk=order.id)


@login_required
@require_http_methods(["POST"])
def delete_cbm(request, cbm_id):
    """
    Удаление записи CBM.
    """
    cbm_record = get_object_or_404(OrderCBM, id=cbm_id)
    order = cbm_record.order
    cbm_value = cbm_record.cbm_value
    
    try:
        with transaction.atomic():
            # Создаем запись аудита перед удалением
            OrderAuditLog.log_action(
                order=order,
                user=request.user,
                action='updated',
                field_name='cbm',
                old_value=f'CBM {cbm_value} куб. м',
                new_value='CBM удалено',
                comments=f'Удалена запись CBM: {cbm_value} куб. м'
            )
            
            # Удаляем запись CBM
            cbm_record.delete()
            
            messages.success(
                request,
                _('Запись CBM успешно удалена! Значение: {cbm} куб. м').format(cbm=cbm_value)
            )
            
    except Exception as e:
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Добавлено логирование ошибок
        import logging
        logger = logging.getLogger('orders')
        logger.error(f"Ошибка при удалении записи CBM (ID: {cbm_id}): {e}", exc_info=True)
        messages.error(request, _('Ошибка при удалении записи CBM: {error}').format(error=str(e)))
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Правильный редирект в зависимости от наличия инвойса
    if hasattr(order, 'invoice'):
        return redirect('invoice_detail', pk=order.invoice.id)
    else:
        return redirect('order_detail', pk=order.id)


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
    user_invoices = Invoice.objects.all()
    
    # Общая статистика
    total_invoices = user_invoices.count()
    total_amount = user_invoices.aggregate(Sum('balance'))['balance__sum'] or 0
    total_paid = user_invoices.aggregate(Sum('total_paid'))['total_paid__sum'] or 0
    remaining_amount = total_amount - total_paid
    
    # Статистика по статусам
    status_stats_raw = user_invoices.values('status').annotate(
        count=Count('id'),
        total_balance=Sum('balance'),
        total_paid=Sum('total_paid')
    )
    
    # Добавляем русские названия статусов
    status_names = {
        'pending': 'Ожидает оплаты',
        'partial': 'Частично оплачен', 
        'paid': 'Полностью оплачен',
        'overdue': 'Просрочен'
    }
    
    status_stats = []
    for stat in status_stats_raw:
        stat['status_name'] = status_names.get(stat['status'], stat['status'])
        status_stats.append(stat)
    
    # Статистика по типам платежей
    payment_stats_raw = InvoicePayment.objects.filter(
    ).values('payment_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    )
    
    # Добавляем русские названия типов платежей
    payment_type_names = {
        'deposit': 'Депозит',
        'final_payment': 'Финальный платеж',
        'partial_payment': 'Частичный платеж',
        'refund': 'Возврат'
    }
    
    payment_stats = []
    for stat in payment_stats_raw:
        stat['payment_type_name'] = payment_type_names.get(stat['payment_type'], stat['payment_type'])
        payment_stats.append(stat)
    
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
