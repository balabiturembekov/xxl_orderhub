# 🚀 Руководство разработчика XXL OrderHub

## 📋 Содержание

1. [Архитектура проекта](#архитектура-проекта)
2. [Структура кода](#структура-кода)
3. [Модули и их назначение](#модули-и-их-назначение)
4. [Конвенции кодирования](#конвенции-кодирования)
5. [Добавление новых функций](#добавление-новых-функций)
6. [Тестирование](#тестирование)
7. [Развертывание](#развертывание)

## 🏗 Архитектура проекта

XXL OrderHub построен на Django с использованием следующих технологий:

- **Backend**: Django 5.2.6, Python 3.13+
- **Database**: PostgreSQL (production), SQLite (development)
- **Cache**: Redis
- **Task Queue**: Celery + Celery Beat
- **Web Server**: Nginx (reverse proxy)
- **Containerization**: Docker + Docker Compose
- **Frontend**: Bootstrap 5, jQuery

### Принципы архитектуры

1. **Модульность**: Код разделен на логические модули по функциональности
2. **Разделение ответственности**: Каждый модуль отвечает за свою область
3. **Документированность**: Все функции и классы имеют docstrings
4. **Типизация**: Использование type hints для лучшей читаемости
5. **Кэширование**: Оптимизация производительности через кэширование

## 📁 Структура кода

```
xxl_orderhub/
├── orders/                          # Основное приложение
│   ├── views/                       # Модули представлений
│   │   ├── __init__.py              # Импорты всех views
│   │   ├── order_views.py           # CRUD операции с заказами
│   │   ├── confirmation_views.py    # Система подтверждений
│   │   ├── notification_views.py   # Управление уведомлениями
│   │   ├── analytics_views.py      # Аналитика и отчеты
│   │   ├── management_views.py     # Управление справочниками
│   │   ├── auth_views.py           # Аутентификация
│   │   └── api_views.py            # AJAX API endpoints
│   ├── models.py                   # Модели данных
│   ├── forms.py                    # Django формы
│   ├── tasks.py                    # Celery задачи
│   ├── analytics.py                # Аналитические функции
│   ├── email_utils.py              # Утилиты для email
│   ├── file_preview.py             # Предварительный просмотр файлов
│   ├── validators.py               # Валидаторы файлов
│   ├── email_backend.py            # Кастомный email backend
│   ├── middleware.py               # Кастомные middleware
│   ├── context_processors.py       # Контекстные процессоры
│   ├── templatetags/               # Кастомные template tags
│   ├── management/commands/        # Django management команды
│   └── tests/                      # Тесты
├── templates/                      # HTML шаблоны
├── static/                        # Статические файлы
├── locale/                        # Переводы
└── xxl_orderhub/                  # Настройки проекта
```

## 🔧 Модули и их назначение

### 1. Order Views (`order_views.py`)

**Назначение**: CRUD операции с заказами

**Основные функции**:
- `OrderListView` - Список заказов с фильтрацией
- `OrderDetailView` - Детальная информация о заказе
- `create_order` - Создание нового заказа
- `download_file` - Скачивание файлов заказа
- `preview_file` - Предварительный просмотр файлов

**Особенности**:
- Оптимизированные запросы с `select_related`
- Кэширование статистики
- Валидация доступа к файлам

### 2. Confirmation Views (`confirmation_views.py`)

**Назначение**: Система подтверждений критических операций

**Основные функции**:
- `send_order` - Подтверждение отправки заказа
- `upload_invoice` - Подтверждение загрузки инвойса
- `complete_order` - Подтверждение завершения заказа
- `confirmation_approve` - Выполнение подтвержденной операции
- `confirmation_reject` - Отклонение операции

**Особенности**:
- Двухэтапный процесс (создание → подтверждение → выполнение)
- Аудит всех операций
- Автоматическое истечение подтверждений

### 3. Notification Views (`notification_views.py`)

**Назначение**: Управление уведомлениями

**Основные функции**:
- `NotificationListView` - Список уведомлений
- `mark_notification_read` - Отметка как прочитанное
- `notification_settings` - Настройки уведомлений
- `test_notification` - Тестирование системы

**Особенности**:
- AJAX обновления
- Настройки пользователя
- Email уведомления

### 4. Analytics Views (`analytics_views.py`)

**Назначение**: Аналитика и отчеты

**Основные функции**:
- `AnalyticsDashboardView` - Дашборд аналитики
- `analytics_export` - Экспорт данных в CSV
- `analytics_api` - API для графиков

**Особенности**:
- Кэширование статистики
- Экспорт данных
- JSON API для фронтенда

### 5. Management Views (`management_views.py`)

**Назначение**: Управление справочниками

**Основные функции**:
- CRUD операции для стран и фабрик
- AJAX endpoints для динамических форм
- Валидация связей

**Особенности**:
- Проверка связанных объектов при удалении
- AJAX создание объектов
- Оптимизированные запросы

### 6. Auth Views (`auth_views.py`)

**Назначение**: Аутентификация и главная страница

**Основные функции**:
- `SignUpView` - Регистрация пользователей
- `HomeView` - Главная страница с разным контентом

**Особенности**:
- Автоматический вход после регистрации
- Разный контент для авторизованных/неавторизованных
- Кэширование статистики

### 7. API Views (`api_views.py`)

**Назначение**: AJAX API endpoints

**Основные функции**:
- `get_factories` - Получение фабрик
- `create_country_ajax` - AJAX создание стран
- `get_user_statistics` - Статистика пользователя

**Особенности**:
- JSON responses
- Валидация данных
- Обработка ошибок

## 📝 Конвенции кодирования

### 1. Документирование функций

```python
def function_name(param1: str, param2: int) -> Dict[str, Any]:
    """
    Краткое описание функции.
    
    Подробное описание того, что делает функция,
    какие параметры принимает и что возвращает.
    
    Args:
        param1: Описание параметра 1
        param2: Описание параметра 2
    
    Returns:
        Словарь с результатами
    
    Raises:
        ValueError: Когда параметры неверные
        Http404: Когда объект не найден
    """
    # Реализация функции
    pass
```

### 2. Типизация

```python
from typing import Optional, Dict, Any, List

def process_orders(orders: List[Order]) -> Dict[str, int]:
    """Обработка списка заказов."""
    pass

def get_user_data(user_id: int) -> Optional[Dict[str, Any]]:
    """Получение данных пользователя."""
    pass
```

### 3. Обработка ошибок

```python
def safe_operation():
    """Безопасная операция с обработкой ошибок."""
    try:
        # Основная логика
        result = risky_operation()
        return {'success': True, 'data': result}
    except SpecificException as e:
        logger.error(f"Specific error: {e}")
        return {'success': False, 'error': str(e)}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {'success': False, 'error': 'Произошла неожиданная ошибка'}
```

### 4. Кэширование

```python
from django.core.cache import cache

def get_cached_data(user_id: int) -> Dict[str, Any]:
    """Получение кэшированных данных."""
    cache_key = f"user_data_{user_id}"
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        cached_data = expensive_operation(user_id)
        cache.set(cache_key, cached_data, 300)  # 5 минут
    
    return cached_data
```

## 🆕 Добавление новых функций

### 1. Создание нового view

1. Определите, к какому модулю относится функция
2. Добавьте функцию в соответствующий файл views
3. Добавьте URL в `urls.py`
4. Создайте шаблон (если нужен)
5. Добавьте тесты

### 2. Создание новой модели

1. Добавьте модель в `models.py`
2. Создайте миграцию: `python manage.py makemigrations`
3. Примените миграцию: `python manage.py migrate`
4. Добавьте в админку (`admin.py`)
5. Создайте формы (`forms.py`)

### 3. Добавление нового API endpoint

1. Добавьте функцию в `api_views.py`
2. Добавьте URL в `urls.py`
3. Добавьте обработку ошибок
4. Протестируйте через AJAX

## 🧪 Тестирование

### Запуск тестов

```bash
# Все тесты
python manage.py test

# Конкретное приложение
python manage.py test orders

# Конкретный тест
python manage.py test orders.tests.test_orders.OrderModelTest
```

### Структура тестов

```python
from django.test import TestCase
from django.contrib.auth.models import User
from orders.models import Order

class OrderModelTest(TestCase):
    """Тесты для модели Order."""
    
    def setUp(self):
        """Настройка тестовых данных."""
        self.user = User.objects.create_user('testuser')
        self.factory = Factory.objects.create(name='Test Factory')
    
    def test_order_creation(self):
        """Тест создания заказа."""
        order = Order.objects.create(
            title='Test Order',
            factory=self.factory,
            employee=self.user
        )
        self.assertEqual(order.title, 'Test Order')
        self.assertEqual(order.status, 'uploaded')
```

## 🚀 Развертывание

### Локальная разработка

```bash
# Установка зависимостей
pip install -r requirements.txt

# Настройка базы данных
python manage.py migrate

# Создание суперпользователя
python manage.py createsuperuser

# Запуск сервера
python manage.py runserver
```

### Docker развертывание

```bash
# Сборка и запуск
docker-compose up --build

# Только запуск
docker-compose up

# Остановка
docker-compose down
```

### Продакшен развертывание

```bash
# Использование скрипта развертывания
./deploy.sh

# Ручное развертывание
sudo docker-compose down
sudo docker-compose pull
sudo docker-compose up --build -d
```

## 🔍 Отладка

### Логи

```bash
# Просмотр логов Django
tail -f logs/django.log

# Просмотр логов контейнера
docker-compose logs web

# Просмотр логов Celery
docker-compose logs worker
```

### Отладка в коде

```python
import logging

logger = logging.getLogger(__name__)

def debug_function():
    """Функция с отладочной информацией."""
    logger.debug("Начало выполнения функции")
    logger.info("Информационное сообщение")
    logger.warning("Предупреждение")
    logger.error("Ошибка")
```

## 📚 Полезные команды

### Django

```bash
# Создание миграций
python manage.py makemigrations

# Применение миграций
python manage.py migrate

# Сбор статических файлов
python manage.py collectstatic

# Создание переводов
python manage.py makemessages -l de
python manage.py compilemessages

# Загрузка фикстур
python manage.py loaddata fixture.json
```

### Docker

```bash
# Пересборка контейнера
docker-compose build web

# Выполнение команды в контейнере
docker-compose exec web python manage.py shell

# Просмотр процессов
docker-compose ps

# Очистка
docker-compose down --volumes --remove-orphans
```

## 🤝 Содействие проекту

1. Создайте feature branch
2. Внесите изменения с документацией
3. Добавьте тесты
4. Создайте pull request
5. Дождитесь code review

## 📞 Поддержка

При возникновении вопросов:

1. Проверьте документацию
2. Посмотрите существующий код
3. Обратитесь к команде разработки

---

**Удачной разработки! 🚀**
