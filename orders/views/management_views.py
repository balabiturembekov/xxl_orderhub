"""
Management views for reference data.

This module handles CRUD operations for reference data:
- Country management (create, edit, delete)
- Factory management (create, edit, delete)
- AJAX endpoints for dynamic forms
"""

from typing import Dict, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.generic import ListView, CreateView, UpdateView
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.db.models import Q
import json

from ..models import Country, Factory
from ..forms import CountryForm, FactoryForm


@method_decorator(login_required, name='dispatch')
class CountryListView(ListView):
    """
    Display a list of all countries.
    
    Features:
    - Pagination
    - Order by name
    - Delete confirmation
    """
    model = Country
    template_name = 'orders/country_list.html'
    context_object_name = 'countries'
    paginate_by = 20
    
    def get_queryset(self):
        """Get all countries ordered by name."""
        return Country.objects.all().order_by('name')


@method_decorator(login_required, name='dispatch')
class CountryCreateView(CreateView):
    """
    Create a new country.
    
    Features:
    - Form validation
    - Success message
    - Redirect to country list
    """
    model = Country
    form_class = CountryForm
    template_name = 'orders/country_form.html'
    success_url = reverse_lazy('country_list')
    
    def form_valid(self, form):
        """Handle successful form submission."""
        response = super().form_valid(form)
        messages.success(self.request, f'Страна "{self.object.name}" успешно создана!')
        return response


@method_decorator(login_required, name='dispatch')
class CountryUpdateView(UpdateView):
    """
    Update an existing country.
    
    Features:
    - Form validation
    - Success message
    - Redirect to country list
    """
    model = Country
    form_class = CountryForm
    template_name = 'orders/country_form.html'
    success_url = reverse_lazy('country_list')
    
    def form_valid(self, form):
        """Handle successful form submission."""
        response = super().form_valid(form)
        messages.success(self.request, f'Страна "{self.object.name}" успешно обновлена!')
        return response


@login_required
def country_delete(request, pk: int):
    """
    Delete a country with confirmation.
    
    Args:
        pk: Country primary key
    
    Returns:
        Rendered confirmation template or redirect to country list
    """
    country = get_object_or_404(Country, pk=pk)
    
    # Check if country has associated factories
    factories_count = country.factory_set.count()
    
    if request.method == 'POST':
        if factories_count > 0:
            messages.error(
                request, 
                f'Нельзя удалить страну "{country.name}", так как к ней привязано {factories_count} фабрик!'
            )
            return redirect('country_list')
        
        country_name = country.name
        country.delete()
        messages.success(request, f'Страна "{country_name}" успешно удалена!')
        return redirect('country_list')
    
    return render(request, 'orders/country_confirm_delete.html', {
        'country': country,
        'factories_count': factories_count
    })


@method_decorator(login_required, name='dispatch')
class FactoryListView(ListView):
    """
    Display a list of all factories.
    
    Features:
    - Pagination
    - Order by name
    - Country filtering
    - Search by name, email, contact person
    - Status filtering (active/inactive)
    - Delete confirmation
    """
    model = Factory
    template_name = 'orders/factory_list.html'
    context_object_name = 'factories'
    paginate_by = 20
    
    def get_queryset(self):
        """Get filtered factories with country information."""
        from django.db.models import Q
        from ..constants import ViewConstants
        
        queryset = Factory.objects.select_related('country')
        
        # Поиск по названию, email, контактному лицу
        search_query = self.request.GET.get('search', '').strip()
        if search_query:
            if len(search_query) > ViewConstants.SEARCH_MAX_LENGTH:
                search_query = search_query[:ViewConstants.SEARCH_MAX_LENGTH]
            
            if len(search_query) >= ViewConstants.SEARCH_MIN_LENGTH:
                queryset = queryset.filter(
                    Q(name__icontains=search_query) |
                    Q(email__icontains=search_query) |
                    Q(contact_person__icontains=search_query)
                )
        
        # Фильтрация по стране
        country_filter = self.request.GET.get('country')
        if country_filter:
            try:
                country_id = int(country_filter)
                if country_id > 0:
                    queryset = queryset.filter(country_id=country_id)
            except (ValueError, TypeError):
                pass  # Игнорируем невалидные значения
        
        # Фильтрация по статусу
        status_filter = self.request.GET.get('status')
        if status_filter == 'active':
            queryset = queryset.filter(is_active=True)
        elif status_filter == 'inactive':
            queryset = queryset.filter(is_active=False)
        
        return queryset.order_by('name')
    
    def get_context_data(self, **kwargs):
        """Add filter options to context."""
        context = super().get_context_data(**kwargs)
        context['countries'] = Country.objects.all().order_by('name')
        context['search_query'] = self.request.GET.get('search', '')
        context['selected_country'] = self.request.GET.get('country', '')
        context['selected_status'] = self.request.GET.get('status', '')
        return context


@method_decorator(login_required, name='dispatch')
class FactoryCreateView(CreateView):
    """
    Create a new factory.
    
    Features:
    - Form validation
    - Success message
    - Redirect to factory list
    """
    model = Factory
    form_class = FactoryForm
    template_name = 'orders/factory_form.html'
    success_url = reverse_lazy('factory_list')
    
    def form_valid(self, form):
        """Handle successful form submission."""
        response = super().form_valid(form)
        messages.success(self.request, f'Фабрика "{self.object.name}" успешно создана!')
        return response


@method_decorator(login_required, name='dispatch')
class FactoryUpdateView(UpdateView):
    """
    Update an existing factory.
    
    Features:
    - Form validation
    - Success message
    - Redirect to factory list
    """
    model = Factory
    form_class = FactoryForm
    template_name = 'orders/factory_form.html'
    success_url = reverse_lazy('factory_list')
    
    def form_valid(self, form):
        """Handle successful form submission."""
        response = super().form_valid(form)
        messages.success(self.request, f'Фабрика "{self.object.name}" успешно обновлена!')
        return response


@login_required
def factory_delete(request, pk: int):
    """
    Delete a factory with confirmation.
    
    Args:
        pk: Factory primary key
    
    Returns:
        Rendered confirmation template or redirect to factory list
    """
    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-58: Используем annotate() для оптимизации запроса
    # Это предотвращает дополнительный SQL запрос для подсчета заказов
    from django.db.models import Count
    
    factory = get_object_or_404(
        Factory.objects.annotate(orders_count=Count('order')),
        pk=pk
    )
    
    # Check if factory has associated orders
    orders_count = factory.orders_count
    
    if request.method == 'POST':
        if orders_count > 0:
            messages.error(
                request, 
                f'Нельзя удалить фабрику "{factory.name}", так как к ней привязано {orders_count} заказов!'
            )
            return redirect('factory_list')
        
        factory_name = factory.name
        factory.delete()
        messages.success(request, f'Фабрика "{factory_name}" успешно удалена!')
        return redirect('factory_list')
    
    return render(request, 'orders/factory_confirm_delete.html', {
        'factory': factory,
        'orders_count': orders_count
    })


# AJAX API endpoints for dynamic forms

@login_required
def get_countries(request):
    """
    AJAX endpoint to get all countries as JSON.
    
    Used for dynamic form population and filtering.
    
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
def create_country_ajax(request):
    """
    AJAX endpoint to create a new country.
    
    Returns:
        JsonResponse with success status and country data
    """
    if request.method == 'POST':
        form = CountryForm(request.POST)
        if form.is_valid():
            country = form.save()
            return JsonResponse({
                'success': True,
                'country': {
                    'id': country.id,
                    'name': country.name,
                    'code': country.code
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def create_factory_ajax(request):
    """
    AJAX endpoint to create a new factory.
    
    Returns:
        JsonResponse with success status and factory data
    """
    if request.method == 'POST':
        form = FactoryForm(request.POST)
        if form.is_valid():
            factory = form.save()
            return JsonResponse({
                'success': True,
                'factory': {
                    'id': factory.id,
                    'name': factory.name,
                    'email': factory.email,
                    'country': {
                        'id': factory.country.id if factory.country else None,
                        'name': factory.country.name if factory.country else None
                    }
                }
            })
        else:
            return JsonResponse({
                'success': False,
                'errors': form.errors
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def get_factories(request):
    """
    AJAX endpoint to get factories filtered by country.
    
    Args:
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
                'id': factory.country.id if factory.country else None,
                'name': factory.country.name if factory.country else None
            }
        }
        for factory in factories
    ]
    
    return JsonResponse({'factories': factories_data})
