import time
import logging
from django.core.cache import cache
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from .constants import ApiConstants

logger = logging.getLogger('orders')


class RequestLoggingMiddleware(MiddlewareMixin):
    """Middleware для логирования запросов"""
    
    def process_request(self, request):
        request.start_time = time.time()
        return None
    
    def process_response(self, request, response):
        if hasattr(request, 'start_time'):
            duration = time.time() - request.start_time
            
            # Логируем только важные запросы
            if request.path.startswith('/orders/') or request.path.startswith('/admin/'):
                logger.info(
                    f"{request.method} {request.path} - "
                    f"Status: {response.status_code} - "
                    f"Duration: {duration:.3f}s - "
                    f"User: {getattr(request.user, 'username', 'Anonymous')} - "
                    f"IP: {self.get_client_ip(request)}"
                )
        
        return response
    
    def get_client_ip(self, request):
        """Получение IP адреса клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class RateLimitMiddleware(MiddlewareMixin):
    """Middleware для ограничения частоты запросов"""
    
    def process_request(self, request):
        # Пропускаем статические файлы, админку и страницы управления
        if (request.path.startswith('/static/') or 
            request.path.startswith('/media/') or
            request.path.startswith('/admin/') or
            request.path.startswith('/countries/') or
            request.path.startswith('/factories/') or
            request.path.startswith('/api/')):
            return None
        
        # Получаем IP адреса
        ip = self.get_client_ip(request)
        
        # Проверяем лимит только для загрузки файлов
        if request.path in ['/orders/create/', '/orders/upload-invoice/']:
            if self.is_rate_limited(ip, 'file_upload', limit=ApiConstants.FILE_UPLOAD_RATE_LIMIT, window=3600):
                logger.warning(f"Rate limit exceeded for file upload from IP: {ip}")
                return HttpResponse("Слишком много загрузок файлов. Попробуйте позже.", status=429)
        
        # Проверяем общий лимит запросов только для API endpoints
        if request.path.startswith('/api/'):
            if self.is_rate_limited(ip, 'api', limit=ApiConstants.API_RATE_LIMIT, window=3600):
                logger.warning(f"Rate limit exceeded for API requests from IP: {ip}")
                return HttpResponse("Слишком много запросов. Попробуйте позже.", status=429)
        
        return None
    
    def is_rate_limited(self, ip, action, limit, window):
        """Проверка превышения лимита"""
        key = f"rate_limit:{action}:{ip}"
        current = cache.get(key, 0)
        
        if current >= limit:
            return True
        
        cache.set(key, current + 1, window)
        return False
    
    def get_client_ip(self, request):
        """Получение IP адреса клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
