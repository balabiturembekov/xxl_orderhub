"""
Middleware для принудительной установки CSRF cookie
"""
from django.middleware.csrf import get_token
from django.utils.deprecation import MiddlewareMixin


class EnsureCSRFCookieMiddleware(MiddlewareMixin):
    """
    Middleware для принудительной установки CSRF cookie
    """
    
    def process_response(self, request, response):
        # Устанавливаем CSRF cookie для всех GET запросов
        if request.method == 'GET' and not request.COOKIES.get('csrftoken'):
            get_token(request)
        return response
