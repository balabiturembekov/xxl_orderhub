"""
Middleware для сжатия ответов
"""
import gzip
from django.utils.deprecation import MiddlewareMixin
from django.http import HttpResponse


class CompressionMiddleware(MiddlewareMixin):
    """
    Middleware для сжатия HTTP ответов
    """
    
    def process_response(self, request, response):
        # Проверяем, поддерживает ли клиент gzip
        accept_encoding = request.META.get('HTTP_ACCEPT_ENCODING', '')
        
        if 'gzip' not in accept_encoding:
            return response
        
        # Проверяем тип контента
        content_type = response.get('Content-Type', '')
        if not any(ct in content_type for ct in ['text/', 'application/json', 'application/javascript']):
            return response
        
        # Проверяем размер ответа
        if len(response.content) < 200:  # Не сжимаем маленькие ответы
            return response
        
        # Сжимаем контент
        try:
            compressed_content = gzip.compress(response.content)
            
            # Создаем новый ответ
            compressed_response = HttpResponse(
                compressed_content,
                content_type=response['Content-Type']
            )
            
            # Копируем заголовки
            for header, value in response.items():
                if header.lower() != 'content-length':
                    compressed_response[header] = value
            
            # Добавляем заголовок сжатия
            compressed_response['Content-Encoding'] = 'gzip'
            compressed_response['Content-Length'] = str(len(compressed_content))
            
            return compressed_response
            
        except Exception:
            # В случае ошибки возвращаем оригинальный ответ
            return response
