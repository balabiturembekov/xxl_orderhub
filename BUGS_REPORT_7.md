# 🐛 Отчет о найденных багах (QA Analysis - Раунд 7)

**Дата анализа:** 2025-12-08  
**Аналитик:** QA Engineer  
**Методология:** Глубокий анализ валидации входных данных и безопасности

---

## 🔴 КРИТИЧЕСКИЙ ПРИОРИТЕТ

### BUG-49: Отсутствие валидации длины search_query - потенциальная DoS атака

**Файл:** `orders/views/order_views.py:673-674`, `orders/views/payment_views.py:834-837`, `orders/views/shipment_views.py:46-51`

**Проблема:**
```python
search_query = self.request.GET.get('search')
if search_query:
    queryset = queryset.filter(
        Q(title__icontains=search_query) |  # ⚠️ НЕТ ОГРАНИЧЕНИЯ ДЛИНЫ!
        Q(description__icontains=search_query) |
        Q(factory__name__icontains=search_query)
    )
```

**Описание:**
Пользователь может отправить очень длинный search_query (например, 10,000 символов), что приведет к:
- Медленным SQL запросам (LIKE с очень длинными строками)
- Высокой нагрузке на БД
- Потенциальной DoS атаке

**Воспроизведение:**
1. Открыть `/orders/?search=` + строка из 10,000 символов
2. Запрос будет выполняться очень долго
3. БД будет перегружена

**Исправление:**
Добавить валидацию длины:
```python
from ..constants import ViewConstants

search_query = self.request.GET.get('search', '').strip()
if search_query:
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-49: Ограничиваем длину поискового запроса
    if len(search_query) > ViewConstants.SEARCH_MAX_LENGTH:
        search_query = search_query[:ViewConstants.SEARCH_MAX_LENGTH]
    
    if len(search_query) >= ViewConstants.SEARCH_MIN_LENGTH:
        queryset = queryset.filter(
            Q(title__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(factory__name__icontains=search_query)
        )
```

---

### BUG-50: Использование @csrf_exempt в API views - потенциальная CSRF уязвимость

**Файл:** `orders/views/api_views.py:85, 153`

**Проблема:**
```python
@csrf_exempt  # ⚠️ ОТКЛЮЧЕНА CSRF ЗАЩИТА!
def create_country_ajax(request):
```

**Описание:**
Хотя есть `@login_required`, отключение CSRF защиты может быть использовано для CSRF атак, если злоумышленник заставит авторизованного пользователя выполнить запрос.

**Воспроизведение:**
1. Злоумышленник создает сайт с формой, которая отправляет POST на `/api/create-country-ajax/`
2. Авторизованный пользователь открывает этот сайт
3. Форма автоматически отправляется, создавая страну без ведома пользователя

**Исправление:**
Использовать CSRF токен через заголовок в AJAX запросах вместо `@csrf_exempt`:
```python
from django.views.decorators.csrf import csrf_protect

@csrf_protect  # Включаем CSRF защиту
def create_country_ajax(request):
    # CSRF токен должен передаваться через заголовок X-CSRFToken в AJAX запросах
```

---

## 🟠 ВЫСОКИЙ ПРИОРИТЕТ

### BUG-51: Отсутствие валидации limit в search_factories

**Файл:** `orders/views/api_views.py:332-338`

**Проблема:**
```python
query = request.GET.get('q', '').strip()
try:
    limit = int(request.GET.get('limit', 10))
    if limit < 1 or limit > 100:
        limit = 10  # ⚠️ Может быть отрицательным или очень большим до проверки!
except (ValueError, TypeError):
    limit = 10
```

**Описание:**
Хотя есть проверка `limit < 1 or limit > 100`, но если передать очень большое число (например, 999999), оно сначала преобразуется в int, что может вызвать проблемы. Также отсутствует валидация длины `query`.

**Исправление:**
```python
from ..constants import ViewConstants

query = request.GET.get('q', '').strip()
# КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-49: Ограничиваем длину поискового запроса
if len(query) > ViewConstants.SEARCH_MAX_LENGTH:
    query = query[:ViewConstants.SEARCH_MAX_LENGTH]

try:
    limit = int(request.GET.get('limit', 10))
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-51: Более строгая валидация limit
    if limit < 1:
        limit = 1
    elif limit > ViewConstants.MAX_PAGE_SIZE:
        limit = ViewConstants.MAX_PAGE_SIZE
except (ValueError, TypeError):
    limit = 10
```

---

### BUG-52: Отсутствие валидации длины rejection_reason

**Файл:** `orders/views/confirmation_views.py:738-740`

**Проблема:**
```python
rejection_reason = request.POST.get('rejection_reason', '')
if not rejection_reason.strip():
    messages.error(request, 'Необходимо указать причину отклонения!')
    # ⚠️ НЕТ ПРОВЕРКИ ДЛИНЫ!
```

**Описание:**
Пользователь может отправить очень длинную причину отклонения (например, 10,000 символов), что может вызвать проблемы с БД или отображением.

**Исправление:**
Добавить валидацию длины:
```python
rejection_reason = request.POST.get('rejection_reason', '').strip()
if not rejection_reason:
    messages.error(request, 'Необходимо указать причину отклонения!')
    return render(request, 'orders/confirmation_reject.html', {
        'confirmation': confirmation,
    })

# КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-52: Ограничиваем длину причины отклонения
MAX_REJECTION_REASON_LENGTH = 2000  # Соответствует max_length в модели
if len(rejection_reason) > MAX_REJECTION_REASON_LENGTH:
    messages.error(request, f'Причина отклонения слишком длинная. Максимум {MAX_REJECTION_REASON_LENGTH} символов.')
    return render(request, 'orders/confirmation_reject.html', {
        'confirmation': confirmation,
    })
```

---

### BUG-53: Отсутствие валидации для year и month в EFacturaBasketListView

**Файл:** `orders/views/efactura_views.py:54-69`

**Проблема:**
```python
year = self.request.GET.get('year')
if year:
    try:
        year = int(year)  # ⚠️ Может быть любое число!
        queryset = queryset.filter(year=year)
    except (ValueError, TypeError):
        pass  # Игнорируем невалидные значения
```

**Описание:**
Пользователь может передать любое значение year (например, -1000 или 99999), что может вызвать проблемы с производительностью или логические ошибки.

**Исправление:**
Добавить валидацию диапазона:
```python
year = self.request.GET.get('year')
if year:
    try:
        year = int(year)
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-53: Валидация диапазона года
        if 2000 <= year <= 2100:
            queryset = queryset.filter(year=year)
    except (ValueError, TypeError):
        pass

month = self.request.GET.get('month')
if month:
    try:
        month = int(month)
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-53: Валидация диапазона месяца
        if 1 <= month <= 12:
            queryset = queryset.filter(month=month)
    except (ValueError, TypeError):
        pass
```

---

## 🟡 СРЕДНИЙ ПРИОРИТЕТ

### BUG-54: Потенциальная проблема с обработкой IntegrityError в get_or_create_for_month

**Файл:** `orders/models.py:1559-1577`

**Проблема:**
```python
try:
    basket, created = cls.objects.get_or_create(
        month=month,
        year=year,
        defaults={...}
    )
except Exception as e:  # ⚠️ Слишком общий Exception!
    try:
        basket = cls.objects.get(month=month, year=year)
        created = False
    except cls.DoesNotExist:
        raise  # Пробрасываем исходную ошибку
```

**Описание:**
Использование общего `Exception` может скрыть другие ошибки, не связанные с IntegrityError. Также может быть race condition, если между `get_or_create` и `get` другой процесс удалит корзину.

**Исправление:**
Обрабатывать только IntegrityError:
```python
from django.db import IntegrityError

try:
    basket, created = cls.objects.get_or_create(
        month=month,
        year=year,
        defaults={...}
    )
except IntegrityError:
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-54: Обрабатываем только IntegrityError
    # Используем select_for_update для предотвращения race condition
    basket = cls.objects.select_for_update().get(month=month, year=year)
    created = False
except Exception as e:
    # Другие ошибки пробрасываем дальше
    raise
```

---

### BUG-55: Отсутствие валидации для factory_id и country_id в OrderListView

**Файл:** `orders/views/order_views.py:660-671`

**Проблема:**
```python
if factory_filter:
    try:
        factory_id = int(factory_filter)  # ⚠️ Может быть отрицательным или очень большим!
        queryset = queryset.filter(factory_id=factory_id)
    except (ValueError, TypeError):
        pass
```

**Описание:**
Пользователь может передать отрицательное или очень большое число, что может вызвать проблемы с производительностью или логические ошибки.

**Исправление:**
Добавить валидацию диапазона:
```python
if factory_filter:
    try:
        factory_id = int(factory_filter)
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-55: Валидация factory_id
        if factory_id > 0:
            queryset = queryset.filter(factory_id=factory_id)
    except (ValueError, TypeError):
        pass

if country_filter:
    try:
        country_id = int(country_filter)
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-55: Валидация country_id
        if country_id > 0:
            queryset = queryset.filter(factory__country_id=country_id)
    except (ValueError, TypeError):
        pass
```

---

### BUG-56: Отсутствие валидации для country_id в get_factories

**Файл:** `orders/views/api_views.py:37-40`

**Проблема:**
```python
country_id = request.GET.get('country_id')

if country_id:
    factories = Factory.objects.filter(country_id=country_id).select_related('country')
    # ⚠️ НЕТ ВАЛИДАЦИИ country_id!
```

**Описание:**
Пользователь может передать невалидное значение country_id (отрицательное, очень большое, строку), что может вызвать ошибку или проблемы с производительностью.

**Исправление:**
Добавить валидацию:
```python
country_id = request.GET.get('country_id')

if country_id:
    try:
        country_id = int(country_id)
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-56: Валидация country_id
        if country_id > 0:
            factories = Factory.objects.filter(country_id=country_id).select_related('country')
        else:
            factories = Factory.objects.select_related('country')
    except (ValueError, TypeError):
        factories = Factory.objects.select_related('country')
else:
    factories = Factory.objects.select_related('country')
```

---

## 📊 Сводка

**Всего найдено:** 8 багов
- 🔴 Критический: 2
- 🟠 Высокий: 3
- 🟡 Средний: 3

**Категории:**
- Валидация входных данных: 6
- Безопасность (CSRF): 1
- Обработка исключений: 1

---

## ✅ Рекомендации

1. **Добавить валидацию длины** для всех пользовательских входных данных
2. **Использовать константы** из `ViewConstants` для ограничений
3. **Заменить `@csrf_exempt`** на `@csrf_protect` с передачей токена через заголовок
4. **Валидировать диапазоны** для всех числовых параметров
5. **Обрабатывать только специфичные исключения** вместо общего `Exception`

---

**Следующие шаги:**
1. Исправить валидацию входных данных во всех views
2. Заменить `@csrf_exempt` на безопасную альтернативу
3. Добавить валидацию диапазонов для всех числовых параметров
4. Протестировать защиту от DoS атак

