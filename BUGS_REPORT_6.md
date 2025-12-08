# 🐛 Отчет о найденных багах (QA Analysis - Раунд 6)

**Дата анализа:** 2025-12-08  
**Аналитик:** QA Engineer  
**Методология:** Глубокий анализ производительности и оптимизации запросов

---

## 🔴 КРИТИЧЕСКИЙ ПРИОРИТЕТ

### BUG-41: N+1 запрос в `ShipmentDetailView` - множественные `.aggregate()` в цикле

**Файл:** `orders/views/shipment_views.py:128-132`

**Проблема:**
```python
for order in shipment.orders.select_related('factory', 'factory__country').all():
    # Get total CBM from records
    order_cbm = order.cbm_records.aggregate(  # ⚠️ N+1 запрос!
        total=Sum('cbm_value')
    )['total'] or Decimal('0')
```

**Описание:**
В цикле для каждого заказа выполняется отдельный запрос `.aggregate()` к `cbm_records`. Если в shipment 100 заказов, будет выполнено 100+ запросов к БД вместо одного.

**Воспроизведение:**
1. Создать shipment с 50+ заказами
2. Открыть страницу деталей shipment
3. Проверить количество SQL запросов через Django Debug Toolbar
4. Увидеть 50+ запросов `SELECT SUM(...) FROM orders_ordercbm WHERE order_id = X`

**Исправление:**
Использовать `Prefetch` с `Prefetch.objects.aggregate()` или предварительно вычислить CBM для всех заказов одним запросом:
```python
from django.db.models import Prefetch, Sum

# Предварительно вычисляем CBM для всех заказов одним запросом
orders_with_cbm = shipment.orders.select_related('factory', 'factory__country').annotate(
    total_cbm=Sum('cbm_records__cbm_value')
)

for order in orders_with_cbm:
    order_cbm = order.total_cbm or Decimal('0')
```

---

### BUG-42: Отсутствие индексов на часто используемых полях

**Файл:** `orders/models.py:212-220`

**Проблема:**
```python
class Meta:
    indexes = [
        models.Index(fields=['cancelled_by_client'], name='order_cancelled_idx'),
        models.Index(fields=['cancelled_by_client_at'], name='order_cancelled_at_idx'),
        models.Index(fields=['cancelled_by_client', 'cancelled_by_client_at'], name='order_cancelled_comp_idx'),
    ]
    # ⚠️ НЕТ ИНДЕКСОВ НА:
    # - status (используется в фильтрах везде)
    # - uploaded_at (используется в ordering и фильтрах)
    # - employee (используется в фильтрах)
    # - factory (используется в фильтрах)
```

**Описание:**
Отсутствуют индексы на полях, которые часто используются в запросах:
- `status` - фильтруется в большинстве views
- `uploaded_at` - используется в `ordering` и фильтрах по датам
- `employee` - фильтруется в `HomeView`, `AnalyticsView`
- `factory` - фильтруется в `OrderListView`, `AnalyticsView`

**Воспроизведение:**
1. Создать 10,000+ заказов
2. Открыть `OrderListView` с фильтром по статусу
3. Проверить EXPLAIN запроса - увидеть `Seq Scan` вместо `Index Scan`
4. Запрос будет медленным (100ms+ вместо 10ms)

**Исправление:**
Добавить индексы:
```python
class Meta:
    indexes = [
        models.Index(fields=['cancelled_by_client'], name='order_cancelled_idx'),
        models.Index(fields=['cancelled_by_client_at'], name='order_cancelled_at_idx'),
        models.Index(fields=['cancelled_by_client', 'cancelled_by_client_at'], name='order_cancelled_comp_idx'),
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-42: Добавляем индексы на часто используемые поля
        models.Index(fields=['status'], name='order_status_idx'),
        models.Index(fields=['uploaded_at'], name='order_uploaded_at_idx'),
        models.Index(fields=['employee'], name='order_employee_idx'),
        models.Index(fields=['factory'], name='order_factory_idx'),
        # Составные индексы для частых комбинаций
        models.Index(fields=['status', 'uploaded_at'], name='order_status_uploaded_idx'),
        models.Index(fields=['employee', 'status'], name='order_employee_status_idx'),
    ]
```

---

## 🟠 ВЫСОКИЙ ПРИОРИТЕТ

### BUG-43: Множественные вызовы `.count()` без оптимизации

**Файл:** `orders/views/payment_views.py:275, 292, 847-855`

**Проблема:**
```python
# В InvoiceDetailView.get_context_data()
payments = invoice.payments.all().order_by('-payment_date', '-created_at')
# ...
context['total_payments'] = payments.count()  # ⚠️ Отдельный запрос COUNT

# В InvoiceListView.get_context_data()
context['total_invoices'] = queryset.count()  # ⚠️ Отдельный запрос
context['pending_invoices'] = queryset.filter(status='pending').count()  # ⚠️ Еще один запрос
context['partial_invoices'] = queryset.filter(status='partial').count()  # ⚠️ Еще один запрос
context['paid_invoices'] = queryset.filter(status='paid').count()  # ⚠️ Еще один запрос
```

**Описание:**
Множественные вызовы `.count()` создают отдельные SQL запросы. Для `InvoiceListView` это 5+ запросов вместо одного с использованием `aggregate()`.

**Воспроизведение:**
1. Открыть страницу списка инвойсов
2. Проверить количество SQL запросов
3. Увидеть 5+ запросов `SELECT COUNT(*) FROM orders_invoice WHERE ...`

**Исправление:**
Использовать один запрос с `aggregate()`:
```python
from django.db.models import Count, Q

stats = queryset.aggregate(
    total_invoices=Count('id'),
    pending_invoices=Count('id', filter=Q(status='pending')),
    partial_invoices=Count('id', filter=Q(status='partial')),
    paid_invoices=Count('id', filter=Q(status='paid')),
    overdue_invoices=Count('id', filter=Q(status__in=['pending', 'partial'], due_date__lt=timezone.now().date())),
)

context.update(stats)
```

---

### BUG-44: Отсутствие индекса на `EFacturaBasket(year, month)`

**Файл:** `orders/models.py:1540-1560` (EFacturaBasket)

**Проблема:**
```python
class EFacturaBasket(models.Model):
    year = models.IntegerField()
    month = models.IntegerField()
    # ...
    class Meta:
        ordering = ['-year', '-month', '-created_at']
        # ⚠️ НЕТ ИНДЕКСА НА (year, month)!
```

**Описание:**
В `EFacturaBasketListView` фильтрация идет по `year` и `month`, но нет индекса на эти поля. При большом количестве корзин запросы будут медленными.

**Воспроизведение:**
1. Создать 1000+ корзин E-Factura
2. Открыть список корзин с фильтром по году и месяцу
3. Проверить EXPLAIN - увидеть `Seq Scan`

**Исправление:**
Добавить индекс:
```python
class Meta:
    ordering = ['-year', '-month', '-created_at']
    indexes = [
        models.Index(fields=['year', 'month'], name='efactura_basket_year_month_idx'),
        models.Index(fields=['created_by'], name='efactura_basket_created_by_idx'),
    ]
```

---

### BUG-45: Неоптимизированный запрос в `EFacturaBasketListView.get_context_data()`

**Файл:** `orders/views/efactura_views.py:76`

**Проблема:**
```python
def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    context['years'] = EFacturaBasket.objects.values_list('year', flat=True).distinct().order_by('-year')
    # ⚠️ Отдельный запрос к БД при каждом запросе страницы
```

**Описание:**
Список годов загружается из БД при каждом запросе страницы, даже если данные не изменились. Это можно кэшировать.

**Воспроизведение:**
1. Открыть список корзин E-Factura
2. Обновить страницу 10 раз
3. Проверить количество запросов - будет 10 одинаковых запросов `SELECT DISTINCT year FROM ...`

**Исправление:**
Использовать кэширование:
```python
from django.core.cache import cache

def get_context_data(self, **kwargs):
    context = super().get_context_data(**kwargs)
    
    # Кэшируем список годов на 1 час
    cache_key = 'efactura_basket_years'
    years = cache.get(cache_key)
    if years is None:
        years = list(EFacturaBasket.objects.values_list('year', flat=True).distinct().order_by('-year'))
        cache.set(cache_key, years, 3600)  # 1 час
    
    context['years'] = years
    context['months'] = list(range(1, 13))
    context['selected_year'] = self.request.GET.get('year', '')
    context['selected_month'] = self.request.GET.get('month', '')
    return context
```

---

## 🟡 СРЕДНИЙ ПРИОРИТЕТ

### BUG-46: Отсутствие индекса на `OrderConfirmation(status, expires_at)`

**Файл:** `orders/models.py:476-520` (OrderConfirmation)

**Проблема:**
```python
class OrderConfirmation(models.Model):
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    expires_at = models.DateTimeField()
    # ...
    class Meta:
        # ⚠️ НЕТ ИНДЕКСА НА (status, expires_at)!
```

**Описание:**
В коде часто используется запрос:
```python
OrderConfirmation.objects.filter(
    order=order,
    action='upload_invoice',
    status='pending',
    expires_at__gt=timezone.now()
).first()
```

Без индекса на `(status, expires_at)` этот запрос будет медленным при большом количестве подтверждений.

**Исправление:**
Добавить индекс:
```python
class Meta:
    indexes = [
        models.Index(fields=['status', 'expires_at'], name='confirmation_status_expires_idx'),
        models.Index(fields=['order', 'status'], name='confirmation_order_status_idx'),
    ]
```

---

### BUG-47: Отсутствие индекса на `Invoice(status, due_date)`

**Файл:** `orders/models.py:921-1000` (Invoice)

**Проблема:**
```python
class Invoice(models.Model):
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(blank=True, null=True)
    # ...
    class Meta:
        # ⚠️ НЕТ ИНДЕКСА НА (status, due_date)!
```

**Описание:**
В `InvoiceListView` и других местах часто используется запрос для поиска просроченных инвойсов:
```python
queryset.filter(
    status__in=['pending', 'partial'],
    due_date__lt=timezone.now().date()
)
```

Без индекса запрос будет медленным.

**Исправление:**
Добавить индекс:
```python
class Meta:
    indexes = [
        models.Index(fields=['status', 'due_date'], name='invoice_status_due_date_idx'),
        models.Index(fields=['order'], name='invoice_order_idx'),
    ]
```

---

### BUG-48: Множественные `.aggregate()` в одном view

**Файл:** `orders/views/payment_views.py:855-872`

**Проблема:**
```python
# В InvoiceListView.get_context_data()
context['total_amount'] = queryset.aggregate(Sum('balance')).get('balance__sum') or 0  # ⚠️ Запрос 1
context['total_paid'] = queryset.aggregate(Sum('total_paid')).get('total_paid__sum') or 0  # ⚠️ Запрос 2

# В invoice_statistics()
total_amount = user_invoices.aggregate(Sum('balance')).get('balance__sum') or 0  # ⚠️ Запрос 1
total_paid = user_invoices.aggregate(Sum('total_paid')).get('total_paid__sum') or 0  # ⚠️ Запрос 2
```

**Описание:**
Множественные вызовы `.aggregate()` создают отдельные SQL запросы. Можно объединить в один запрос.

**Исправление:**
Объединить в один запрос:
```python
stats = queryset.aggregate(
    total_amount=Sum('balance'),
    total_paid=Sum('total_paid'),
)

context['total_amount'] = stats['total_amount'] or 0
context['total_paid'] = stats['total_paid'] or 0
```

---

## 📊 Сводка

**Всего найдено:** 8 багов
- 🔴 Критический: 2
- 🟠 Высокий: 3
- 🟡 Средний: 3

**Категории:**
- Производительность БД: 8
- Отсутствие индексов: 4
- N+1 запросы: 1
- Неоптимизированные запросы: 3

---

## ✅ Рекомендации

1. **Добавить индексы** на все часто используемые поля в фильтрах и сортировках
2. **Использовать `annotate()`** вместо множественных `.aggregate()` в циклах
3. **Кэшировать** редко изменяющиеся данные (списки годов, месяцев)
4. **Объединять** множественные `.aggregate()` в один запрос
5. **Использовать `Prefetch`** для оптимизации обратных связей

---

**Следующие шаги:**
1. Создать миграции для добавления индексов
2. Оптимизировать запросы в views
3. Добавить кэширование для статических данных
4. Протестировать производительность после исправлений

