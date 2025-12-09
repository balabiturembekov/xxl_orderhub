"""
Views for E-Factura Turkey basket management.

This module contains views for managing E-Factura baskets and files:
- Basket listing and filtering
- Basket detail view
- File upload to baskets
- File download from baskets
"""

from typing import Dict, Any
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.views.generic import ListView, DetailView, CreateView
from django.http import HttpResponse, Http404, FileResponse
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.db import transaction
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
import zipfile
import io
from datetime import date

from ..models import EFacturaBasket, EFacturaFile, Order, OrderAuditLog
from ..forms import EFacturaFileForm


@method_decorator(login_required, name='dispatch')
class EFacturaBasketListView(ListView):
    """
    Display a list of E-Factura baskets.
    
    Features:
    - Filtering by year and month
    - Pagination
    - Order by year and month (newest first)
    """
    model = EFacturaBasket
    template_name = 'orders/efactura_basket_list.html'
    context_object_name = 'baskets'
    paginate_by = 20
    
    def get_paginate_by(self, queryset):
        """
        КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-60: Валидация paginate_by для предотвращения DoS атак.
        Если в будущем будет добавлена возможность изменять размер страницы через параметры,
        это предотвратит очень большие запросы к БД.
        """
        from ..constants import ViewConstants
        
        page_size = self.request.GET.get('page_size', self.paginate_by)
        try:
            page_size = int(page_size)
            if page_size < 1:
                page_size = self.paginate_by
            elif page_size > ViewConstants.MAX_PAGE_SIZE:
                page_size = ViewConstants.MAX_PAGE_SIZE
        except (ValueError, TypeError):
            page_size = self.paginate_by
        return page_size
    
    def get_queryset(self):
        """Get filtered baskets."""
        queryset = EFacturaBasket.objects.annotate(
            files_count=Count('files')
        ).select_related('created_by').order_by('-year', '-month', '-created_at')
        
        # Фильтрация по году
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-53: Валидация диапазона year
        year = self.request.GET.get('year')
        if year:
            try:
                year = int(year)
                if 2000 <= year <= 2100:
                    queryset = queryset.filter(year=year)
            except (ValueError, TypeError):
                pass
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-53: Валидация диапазона month
        month = self.request.GET.get('month')
        if month:
            try:
                month = int(month)
                if 1 <= month <= 12:
                    queryset = queryset.filter(month=month)
            except (ValueError, TypeError):
                pass
        
        return queryset
    
    def get_context_data(self, **kwargs):
        """Add additional context."""
        from django.core.cache import cache
        
        context = super().get_context_data(**kwargs)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-45: Кэшируем список годов на 1 час
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


@method_decorator(login_required, name='dispatch')
class EFacturaBasketDetailView(DetailView):
    """
    Display details of an E-Factura basket.
    
    Shows:
    - Basket information
    - List of files in the basket
    - Upload form for new files
    """
    model = EFacturaBasket
    template_name = 'orders/efactura_basket_detail.html'
    context_object_name = 'basket'
    
    def get_queryset(self):
        """Optimize queries."""
        return EFacturaBasket.objects.prefetch_related(
            'files__order',
            'files__order__factory',
            'files__created_by'
        ).select_related('created_by')
    
    def get_context_data(self, **kwargs):
        """Add files and form to context."""
        context = super().get_context_data(**kwargs)
        basket = self.get_object()
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-57: Используем len() для уже загруженных объектов
        # prefetch_related('files') в get_queryset уже загрузил все файлы
        files_list = list(basket.files.all())
        context['files'] = sorted(files_list, key=lambda f: (f.upload_date or date.min, f.created_at), reverse=True)
        # Передаем basket в форму для фильтрации заказов
        context['form'] = EFacturaFileForm(basket=basket)
        # Используем len() вместо count() для уже загруженных объектов
        context['total_files'] = len(files_list)
        return context


@login_required
@require_http_methods(["POST"])
def upload_efactura_file(request, basket_id: int):
    """
    Upload a file to an E-Factura basket.
    
    Args:
        basket_id: EFacturaBasket primary key
    
    Returns:
        Redirect to basket detail page
    """
    basket = get_object_or_404(EFacturaBasket, pk=basket_id)
    
    form = EFacturaFileForm(request.POST, request.FILES, basket=basket)
    
    if form.is_valid():
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем, что заказ действительно турецкий и имеет e_factura_turkey=True
        order = form.cleaned_data.get('order')
        if not order:
            messages.error(request, 'Необходимо выбрать заказ!')
            return redirect('efactura_basket_detail', pk=basket_id)
        
        # Проверки валидности заказа
        if not order.is_turkish_factory:
            messages.error(request, 'Можно добавлять файлы только для заказов турецких фабрик!')
            return redirect('efactura_basket_detail', pk=basket_id)
        
        if not order.e_factura_turkey:
            messages.error(request, 'Можно добавлять файлы только для заказов с выбранным E-Factura Turkey!')
            return redirect('efactura_basket_detail', pk=basket_id)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем, что файл загружен
        if 'file' not in request.FILES or not request.FILES['file']:
            messages.error(request, 'Необходимо выбрать файл для загрузки!')
            return redirect('efactura_basket_detail', pk=basket_id)
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверка размера файла (максимум 50MB)
        uploaded_file = request.FILES['file']
        max_size = 50 * 1024 * 1024  # 50MB
        if uploaded_file.size > max_size:
            messages.error(request, f'Размер файла превышает максимально допустимый (50MB). Размер файла: {uploaded_file.size / (1024*1024):.2f}MB')
            return redirect('efactura_basket_detail', pk=basket_id)
        
        try:
            with transaction.atomic():
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-4: Используем select_for_update() для атомарной проверки дубликатов
                # Это предотвращает race condition при одновременной загрузке файлов
                existing_file = EFacturaFile.objects.select_for_update().filter(
                    basket=basket,
                    order=order
                ).first()
                
                if existing_file:
                    messages.warning(request, f'Файл для заказа "{order.title}" уже существует в этой корзине. Используйте существующий файл или удалите его перед загрузкой нового.')
                    return redirect('efactura_basket_detail', pk=basket_id)
                
                efactura_file = form.save(commit=False)
                efactura_file.basket = basket
                efactura_file.created_by = request.user
                if not efactura_file.upload_date:
                    efactura_file.upload_date = date.today()
                efactura_file.save()
                
                # Создаем audit log для заказа
                if efactura_file.order:
                    OrderAuditLog.log_action(
                        order=efactura_file.order,
                        user=request.user,
                        action='file_uploaded',
                        field_name='efactura_file',
                        new_value=f'Загружен файл E-Factura в корзину {basket.name}',
                        comments=f'Файл E-Factura загружен в корзину {basket.name}'
                    )
            
            messages.success(request, 'Файл E-Factura успешно загружен в корзину!')
        except (ValueError, TypeError, AttributeError) as e:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-61: Обрабатываем специфичные ошибки валидации
            import logging
            logger = logging.getLogger('orders')
            logger.error(f"Ошибка валидации при загрузке файла E-Factura: {e}", exc_info=True)
            messages.error(request, f'Ошибка валидации: {str(e)}')
        except (IOError, OSError) as e:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-61: Обрабатываем ошибки файловой системы отдельно
            import logging
            logger = logging.getLogger('orders')
            logger.error(f"Ошибка файловой системы при загрузке файла E-Factura: {e}", exc_info=True)
            messages.error(request, 'Ошибка при работе с файлом. Попробуйте еще раз.')
        except Exception as e:
            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-61: Общий обработчик только для неожиданных ошибок
            import logging
            logger = logging.getLogger('orders')
            logger.exception(f"Неожиданная ошибка при загрузке файла E-Factura: {e}")
            messages.error(request, 'Произошла неожиданная ошибка. Обратитесь к администратору.')
            raise  # Пробрасываем дальше для обработки на верхнем уровне
    else:
        messages.error(request, 'Ошибка при загрузке файла. Проверьте форму.')
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f'{field}: {error}')
    
    return redirect('efactura_basket_detail', pk=basket_id)


@login_required
def download_efactura_file(request, file_id: int):
    """
    Download a single E-Factura file.
    
    Args:
        file_id: EFacturaFile primary key
    
    Returns:
        FileResponse with the file
    """
    efactura_file = get_object_or_404(EFacturaFile, pk=file_id)
    
    if not efactura_file.file:
        raise Http404("Файл не найден")
    
    try:
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем доступность файла перед открытием
        if not hasattr(efactura_file.file, 'open'):
            raise Http404("Файл недоступен")
        
        file_handle = efactura_file.file.open('rb')
        response = FileResponse(
            file_handle,
            content_type='application/octet-stream'
        )
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасное извлечение имени файла
        if efactura_file.file.name:
            filename = efactura_file.file.name.split('/')[-1] if '/' in efactura_file.file.name else efactura_file.file.name
            # Убираем небезопасные символы из имени файла
            import re
            filename = re.sub(r'[^\w\s.-]', '', filename)
        else:
            filename = f'efactura_file_{efactura_file.id}'
        response['Content-Disposition'] = f'attachment; filename="{filename}"'
        return response
    except (IOError, OSError, FileNotFoundError) as e:
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-61: Обрабатываем ошибки файловой системы отдельно
        import logging
        logger = logging.getLogger('orders')
        logger.error(f"Ошибка файловой системы при скачивании файла E-Factura {file_id}: {e}", exc_info=True)
        raise Http404("Файл недоступен")
    except Exception as e:
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-61: Общий обработчик только для неожиданных ошибок
        import logging
        logger = logging.getLogger('orders')
        logger.exception(f"Неожиданная ошибка при скачивании файла E-Factura {file_id}: {e}")
        raise Http404("Файл недоступен")


@login_required
def download_all_efactura_files(request, basket_id: int):
    """
    Download all files from a basket as a ZIP archive.
    
    Args:
        basket_id: EFacturaBasket primary key
    
    Returns:
        HttpResponse with ZIP file
    """
    basket = get_object_or_404(EFacturaBasket, pk=basket_id)
    files = basket.files.all()
    
    if not files.exists():
        messages.error(request, 'В корзине нет файлов для скачивания!')
        return redirect('efactura_basket_detail', pk=basket_id)
    
    try:
        # Создаем ZIP архив в памяти
        zip_buffer = io.BytesIO()
        files_added = 0
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for efactura_file in files:
                if efactura_file.file:
                    try:
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-21: Используем порционное чтение для предотвращения утечки памяти
                        # Читаем файл порциями вместо загрузки всего файла в память
                        if not hasattr(efactura_file.file, 'open'):
                            continue
                        
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасное извлечение имени файла
                        if efactura_file.file.name:
                            filename = efactura_file.file.name.split('/')[-1] if '/' in efactura_file.file.name else efactura_file.file.name
                        else:
                            filename = f'efactura_file_{efactura_file.id}'
                        
                        # Используем порционное чтение для больших файлов
                        chunk_size = 8192  # 8KB chunks
                        with efactura_file.file.open('rb') as file_handle:
                            # Создаем временный файл для больших файлов или используем BytesIO для маленьких
                            file_size = efactura_file.file.size if hasattr(efactura_file.file, 'size') else 0
                            
                            if file_size > 10 * 1024 * 1024:  # Если файл больше 10MB
                                # Для больших файлов используем временный файл
                                import tempfile
                                import shutil
                                with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                                    shutil.copyfileobj(file_handle, temp_file, length=chunk_size)
                                    temp_file.seek(0)
                                    with open(temp_file.name, 'rb') as temp_read:
                                        zip_file.writestr(filename, temp_read.read(), compress_type=zipfile.ZIP_DEFLATED)
                                    import os
                                    os.unlink(temp_file.name)
                            else:
                                # Для маленьких файлов используем обычное чтение
                                file_content = file_handle.read()
                                zip_file.writestr(filename, file_content, compress_type=zipfile.ZIP_DEFLATED)
                            
                            files_added += 1
                    except (IOError, OSError, FileNotFoundError) as e:
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-61: Обрабатываем ошибки файловой системы отдельно
                        import logging
                        logger = logging.getLogger('orders')
                        logger.error(f"Ошибка файловой системы при добавлении файла {efactura_file.id} в ZIP: {e}", exc_info=True)
                        continue
                    except Exception as e:
                        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-61: Общий обработчик только для неожиданных ошибок
                        import logging
                        logger = logging.getLogger('orders')
                        logger.exception(f"Неожиданная ошибка при добавлении файла {efactura_file.id} в ZIP: {e}")
                        continue
        
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверяем, что хотя бы один файл был добавлен
        if files_added == 0:
            messages.error(request, 'Не удалось добавить файлы в архив!')
            return redirect('efactura_basket_detail', pk=basket_id)
        
        zip_buffer.seek(0)
        
        # Создаем HTTP ответ с ZIP файлом
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасное формирование имени файла с учетом кодировки
        import urllib.parse
        safe_basket_name = basket.name.replace(" ", "_").replace("/", "_").replace("\\", "_")
        zip_filename = f"efactura_basket_{safe_basket_name}.zip"
        response = HttpResponse(zip_buffer.read(), content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{zip_filename}"; filename*=UTF-8\'\'{urllib.parse.quote(zip_filename)}'
        return response
    except (IOError, OSError, MemoryError) as e:
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-61: Обрабатываем ошибки файловой системы и памяти отдельно
        import logging
        logger = logging.getLogger('orders')
        logger.error(f"Ошибка файловой системы/памяти при создании ZIP архива для корзины {basket_id}: {e}", exc_info=True)
        messages.error(request, 'Ошибка при создании архива. Возможно, файлы слишком большие.')
        return redirect('efactura_basket_detail', pk=basket_id)
    except Exception as e:
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ BUG-61: Общий обработчик только для неожиданных ошибок
        import logging
        logger = logging.getLogger('orders')
        logger.exception(f"Неожиданная ошибка при создании ZIP архива для корзины {basket_id}: {e}")
        messages.error(request, 'Произошла неожиданная ошибка. Обратитесь к администратору.')
        return redirect('efactura_basket_detail', pk=basket_id)

