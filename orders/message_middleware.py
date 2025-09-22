from django.utils.deprecation import MiddlewareMixin
from django.contrib import messages


class MessageCleanupMiddleware(MiddlewareMixin):
    """
    Middleware для автоматической очистки сообщений после их отображения.
    """
    
    def process_response(self, request, response):
        # Очищаем сообщения только для успешных ответов (статус 200)
        if response.status_code == 200:
            # Получаем все сообщения и помечаем их как использованные
            storage = messages.get_messages(request)
            # Просто итерируемся по сообщениям, чтобы пометить их как использованные
            list(storage)
        
        return response
