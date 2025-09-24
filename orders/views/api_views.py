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
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from django.db.models import Q
import json

from ..models import Order, Factory, Country


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
    country_id = request.GET.get('country_id')
    
    if country_id:
        factories = Factory.objects.filter(country_id=country_id).select_related('country')
    else:
        factories = Factory.objects.select_related('country')
    
    factories_data = [
        {
            'id': factory.id,
            'name': factory.name,
            'email': factory.email,
            'country': {
                'id': factory.country.id,
                'name': factory.country.name,
                'code': factory.country.code
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
    countries = Country.objects.all().order_by('name')
    countries_data = [
        {
            'id': country.id,
            'name': country.name,
            'code': country.code
        }
        for country in countries
    ]
    
    return JsonResponse({'countries': countries_data})


@login_required
@require_http_methods(["POST"])
@csrf_exempt
def create_country_ajax(request):
    """
    Create a new country via AJAX.
    
    Request Body:
        JSON with country data (name, code)
    
    Returns:
        JsonResponse with success status and country data
    """
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        if not data.get('name') or not data.get('code'):
            return JsonResponse({
                'success': False,
                'message': 'Название и код страны обязательны'
            })
        
        # Check if country with this code already exists
        if Country.objects.filter(code=data['code']).exists():
            return JsonResponse({
                'success': False,
                'message': 'Страна с таким кодом уже существует'
            })
        
        # Create country
        country = Country.objects.create(
            name=data['name'],
            code=data['code']
        )
        
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
@csrf_exempt
def create_factory_ajax(request):
    """
    Create a new factory via AJAX.
    
    Request Body:
        JSON with factory data (name, email, country_id)
    
    Returns:
        JsonResponse with success status and factory data
    """
    try:
        data = json.loads(request.body)
        
        # Validate required fields
        if not all([data.get('name'), data.get('email'), data.get('country_id')]):
            return JsonResponse({
                'success': False,
                'message': 'Все поля обязательны'
            })
        
        # Check if country exists
        try:
            country = Country.objects.get(id=data['country_id'])
        except Country.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Страна не найдена'
            })
        
        # Create factory
        factory = Factory.objects.create(
            name=data['name'],
            email=data['email'],
            country=country
        )
        
        return JsonResponse({
            'success': True,
            'factory': {
                'id': factory.id,
                'name': factory.name,
                'email': factory.email,
                'country': {
                    'id': factory.country.id,
                    'name': factory.country.name,
                    'code': factory.country.code
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
    order = get_object_or_404(Order, pk=pk, employee=request.user)
    
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
    user_orders = Order.objects.filter(employee=request.user)
    
    # Calculate basic statistics
    total_orders = user_orders.count()
    orders_by_status = {}
    
    for status, _ in Order.STATUS_CHOICES:
        count = user_orders.filter(status=status).count()
        orders_by_status[status] = count
    
    # Calculate recent activity (last 7 days)
    week_ago = timezone.now() - timezone.timedelta(days=7)
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
    query = request.GET.get('q', '').strip()
    limit = int(request.GET.get('limit', 10))
    
    if not query:
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
                'id': factory.country.id,
                'name': factory.country.name,
                'code': factory.country.code
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
    
    # Get order statistics for this factory
    orders_count = Order.objects.filter(factory=factory).count()
    recent_orders = Order.objects.filter(factory=factory).order_by('-uploaded_at')[:5]
    
    return JsonResponse({
        'id': factory.id,
        'name': factory.name,
        'email': factory.email,
        'contact_person': factory.contact_person,
        'phone': factory.phone,
        'address': factory.address,
        'country': {
            'id': factory.country.id,
            'name': factory.country.name,
            'code': factory.country.code
        },
        'orders_count': orders_count,
        'recent_orders': [
            {
                'id': order.id,
                'title': order.title,
                'status': order.status,
                'status_display': order.get_status_display(),
                'uploaded_at': order.uploaded_at.isoformat(),
            }
            for order in recent_orders
        ]
    })
