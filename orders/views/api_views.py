"""
API views for AJAX endpoints.

This module contains all AJAX API endpoints used by the frontend:
- Dynamic form population
- Real-time data updates
- File operations
- Utility functions
"""

from typing import Dict, Any
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
import json

from ..models import Order, Factory, Country
from ..constants import TimeConstants


@login_required
@require_http_methods(["GET"])
def get_factories(request):
    """
    Get factories filtered by country.
    
    Query Parameters:
        country_id: Optional country ID for filtering
    
    Returns:
        JsonResponse with factories data
    """
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-56: Валидация country_id
    from ..constants import ViewConstants
    
    country_id = request.GET.get('country_id')
    
    if country_id:
        try:
            country_id = int(country_id)
            if country_id > 0:
                factories = Factory.objects.filter(country_id=country_id).select_related('country')
            else:
                factories = Factory.objects.select_related('country')
        except (ValueError, TypeError):
            factories = Factory.objects.select_related('country')
    else:
        factories = Factory.objects.select_related('country')
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-74: Ограничиваем количество результатов
    factories = factories[:ViewConstants.MAX_PAGE_SIZE]
    
    factories_data = [
        {
            'id': factory.id,
            'name': factory.name,
            'email': factory.email,
            'country': {
                'id': factory.country.id if factory.country else None,
                'name': factory.country.name if factory.country else None,
                'code': factory.country.code if factory.country else None
            }
        }
        for factory in factories
    ]
    
    return JsonResponse({'factories': factories_data})


@login_required
@require_http_methods(["GET"])
def get_countries(request):
    """
    Get all countries.
    
    Returns:
        JsonResponse with countries data
    """
    from ..constants import ViewConstants
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-74: Ограничиваем количество результатов
    countries = Country.objects.all().order_by('name')[:ViewConstants.MAX_PAGE_SIZE]
    countries_data = [
        {
            'id': country.id,
            'name': country.name,
            'code': country.code
        }
        for country in countries
    ]
    
    return JsonResponse({'countries': countries_data})


from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie

@login_required
@require_http_methods(["POST"])
@csrf_protect
@ensure_csrf_cookie
def create_country_ajax(request):
    """
    Create a new country via AJAX.
    
    КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-50: Убрали @csrf_exempt, используем стандартную CSRF защиту Django.
    CSRF токен должен передаваться через заголовок X-CSRFToken в AJAX запросах.
    @ensure_csrf_cookie гарантирует установку CSRF cookie для проверки токена.
    
    Request Body:
        JSON with country data (name, code)
    
    Returns:
        JsonResponse with success status and country data
    """
    from django.db import transaction
    
    try:
        data = json.loads(request.body)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-72: Валидация и нормализация полей
        name = data.get('name', '').strip()
        code = data.get('code', '').strip().upper()
        
        # Validate required fields
        if not name or not code:
            return JsonResponse({
                'success': False,
                'message': 'Название и код страны обязательны'
            })
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-72: Валидация длины полей
        if len(name) > 100:  # Согласно модели Country (max_length=100)
            return JsonResponse({
                'success': False,
                'message': 'Название страны слишком длинное (максимум 100 символов)'
            })
        
        if len(code) > 3:  # Согласно модели Country (max_length=3)
            return JsonResponse({
                'success': False,
                'message': 'Код страны слишком длинный (максимум 3 символа)'
            })
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-73: Валидация формата кода страны
        # Код должен быть 2-3 буквы латиницы (ISO 3166-1 alpha-2 или alpha-3)
        import re
        if not re.match(r'^[A-Z]{2,3}$', code):
            return JsonResponse({
                'success': False,
                'message': 'Код страны должен состоять из 2-3 букв латиницы'
            })
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем транзакцию для атомарности операции
        # Это предотвращает race condition при проверке существования и создании
        try:
            with transaction.atomic():
                # Проверяем существование в транзакции с блокировкой
                # Используем get_or_create для атомарности
                country, created = Country.objects.get_or_create(
                    code=code,
                    defaults={'name': name}
                )
                
                if not created:
                    return JsonResponse({
                        'success': False,
                        'message': 'Страна с таким кодом уже существует'
                    })
        except Exception as db_error:
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при создании страны: {str(db_error)}'
            })
        
        return JsonResponse({
            'success': True,
            'country': {
                'id': country.id,
                'name': country.name,
                'code': country.code
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Неверный формат JSON'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при создании страны: {str(e)}'
        })


@login_required
@require_http_methods(["POST"])
@csrf_protect
@ensure_csrf_cookie
def create_factory_ajax(request):
    """
    Create a new factory via AJAX.
    
    КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-50: Убрали @csrf_exempt, используем стандартную CSRF защиту Django.
    CSRF токен должен передаваться через заголовок X-CSRFToken в AJAX запросах.
    @ensure_csrf_cookie гарантирует установку CSRF cookie для проверки токена.
    
    Request Body:
        JSON with factory data (name, email, country_id)
    
    Returns:
        JsonResponse with success status and factory data
    """
    from django.db import transaction
    
    try:
        data = json.loads(request.body)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-72: Валидация и нормализация полей
        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        country_id = data.get('country_id')
        contact_person = data.get('contact_person', '').strip()
        phone = data.get('phone', '').strip()
        address = data.get('address', '').strip()
        
        if not all([name, email, country_id]):
            return JsonResponse({
                'success': False,
                'message': 'Все поля обязательны'
            })
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-72: Валидация длины полей
        if len(name) > 200:  # Согласно модели Factory (max_length=200)
            return JsonResponse({
                'success': False,
                'message': 'Название фабрики слишком длинное (максимум 200 символов)'
            })
        
        if len(email) > 254:  # Стандарт RFC 5321 для email
            return JsonResponse({
                'success': False,
                'message': 'Email адрес слишком длинный (максимум 254 символа)'
            })
        
        if contact_person and len(contact_person) > 100:  # Согласно модели Factory (max_length=100)
            return JsonResponse({
                'success': False,
                'message': 'Имя контактного лица слишком длинное (максимум 100 символов)'
            })
        
        if phone and len(phone) > 50:  # Согласно модели Factory (max_length=50)
            return JsonResponse({
                'success': False,
                'message': 'Телефон слишком длинный (максимум 50 символов)'
            })
        
        if address and len(address) > 10000:  # Разумное ограничение для TextField
            return JsonResponse({
                'success': False,
                'message': 'Адрес слишком длинный (максимум 10000 символов)'
            })
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Валидация email формата
        from django.core.validators import validate_email
        from django.core.exceptions import ValidationError
        try:
            validate_email(email)
        except ValidationError:
            return JsonResponse({
                'success': False,
                'message': 'Неверный формат email адреса'
            })
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем транзакцию для атомарности операции
        # Это предотвращает race condition при проверке существования и создании
        try:
            with transaction.atomic():
                # Проверяем существование страны в транзакции
                try:
                    country = Country.objects.select_for_update().get(id=country_id)
                except Country.DoesNotExist:
                    return JsonResponse({
                        'success': False,
                        'message': 'Страна не найдена'
                    })
                
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверка на уникальность email
                if Factory.objects.filter(email=email).exists():
                    return JsonResponse({
                        'success': False,
                        'message': 'Фабрика с таким email уже существует'
                    })
                
                # Create factory
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Добавляем обработку всех полей из формы
                factory = Factory.objects.create(
                    name=name,
                    email=email,
                    country=country,
                    contact_person=contact_person,
                    phone=phone,
                    address=address,
                    is_active=data.get('is_active', True)  # По умолчанию активна
                )
        except Exception as db_error:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Обработка IntegrityError для дубликатов
            from django.db import IntegrityError
            if isinstance(db_error, IntegrityError):
                return JsonResponse({
                    'success': False,
                    'message': 'Фабрика с таким email или названием уже существует'
                })
            return JsonResponse({
                'success': False,
                'message': f'Ошибка при создании фабрики: {str(db_error)}'
            })
        
        return JsonResponse({
            'success': True,
            'factory': {
                'id': factory.id,
                'name': factory.name,
                'email': factory.email,
                'country': {
                    'id': factory.country.id if factory.country else None,
                    'name': factory.country.name if factory.country else None,
                    'code': factory.country.code if factory.country else None
                }
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Неверный формат JSON'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Ошибка при создании фабрики: {str(e)}'
        })


@login_required
@require_http_methods(["GET"])
def get_order_status(request, pk: int):
    """
    Get current status of an order.
    
    Args:
        pk: Order primary key
    
    Returns:
        JsonResponse with order status information
    """
    order = get_object_or_404(Order, pk=pk)
    
    return JsonResponse({
        'id': order.id,
        'status': order.status,
        'status_display': order.get_status_display(),
        'uploaded_at': order.uploaded_at.isoformat() if order.uploaded_at else None,
        'sent_at': order.sent_at.isoformat() if order.sent_at else None,
        'invoice_received_at': order.invoice_received_at.isoformat() if order.invoice_received_at else None,
        'completed_at': order.completed_at.isoformat() if order.completed_at else None,
    })


@login_required
@require_http_methods(["GET"])
def get_user_statistics(request):
    """
    Get user statistics for dashboard.
    
    Returns:
        JsonResponse with user statistics
    """
    # Исключаем отмененные клиентом заказы из статистики
    # Используем ~Q для безопасной обработки возможных NULL значений
    user_orders = Order.objects.filter(~Q(cancelled_by_client=True))
    
    # Calculate basic statistics
    total_orders = user_orders.count()
    orders_by_status = {}
    
    for status, _ in Order.STATUS_CHOICES:
        count = user_orders.filter(status=status).count()
        orders_by_status[status] = count
    
    # Calculate recent activity (last 7 days)
    week_ago = timezone.now() - timezone.timedelta(days=TimeConstants.LOG_RETENTION_DAYS)
    recent_orders = user_orders.filter(uploaded_at__gte=week_ago).count()
    
    return JsonResponse({
        'total_orders': total_orders,
        'orders_by_status': orders_by_status,
        'recent_orders': recent_orders,
        'week_ago': week_ago.isoformat(),
    })


@login_required
@require_http_methods(["GET"])
def search_factories(request):
    """
    Search factories by name or email.
    
    Query Parameters:
        q: Search query
        limit: Maximum number of results (default: 10)
    
    Returns:
        JsonResponse with matching factories
    """
    from ..constants import ViewConstants
    
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-49 и BUG-51: Валидация query и limit
    query = request.GET.get('q', '').strip()
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
        limit = 10  # Значение по умолчанию при ошибке преобразования
    
    if not query or len(query) < ViewConstants.SEARCH_MIN_LENGTH:
        return JsonResponse({'factories': []})
    
    factories = Factory.objects.filter(
        Q(name__icontains=query) | Q(email__icontains=query)
    ).select_related('country')[:limit]
    
    factories_data = [
        {
            'id': factory.id,
            'name': factory.name,
            'email': factory.email,
            'country': {
                'id': factory.country.id if factory.country else None,
                'name': factory.country.name if factory.country else None,
                'code': factory.country.code if factory.country else None
            }
        }
        for factory in factories
    ]
    
    return JsonResponse({'factories': factories_data})


@login_required
@require_http_methods(["GET"])
def get_factory_details(request, pk: int):
    """
    Get detailed information about a factory.
    
    Args:
        pk: Factory primary key
    
    Returns:
        JsonResponse with factory details
    """
    factory = get_object_or_404(Factory, pk=pk)
    
    # Get order statistics for this factory (исключаем отмененные клиентом)
    # Используем ~Q для безопасной обработки возможных NULL значений
    orders_count = Order.objects.filter(factory=factory).filter(~Q(cancelled_by_client=True)).count()
    recent_orders = Order.objects.filter(factory=factory).filter(~Q(cancelled_by_client=True)).order_by('-uploaded_at')[:5]
    
    return JsonResponse({
        'id': factory.id,
        'name': factory.name,
        'email': factory.email,
        'contact_person': factory.contact_person,
        'phone': factory.phone,
        'address': factory.address,
        'country': {
            'id': factory.country.id if factory.country else None,
            'name': factory.country.name if factory.country else None,
            'code': factory.country.code if factory.country else None
        },
        'orders_count': orders_count,
        'recent_orders': [
            {
                'id': order.id,
                'title': order.title,
                'status': order.status,
                'status_display': order.get_status_display(),
                'uploaded_at': order.uploaded_at.isoformat() if order.uploaded_at else None,
            }
            for order in recent_orders
        ]
    })
