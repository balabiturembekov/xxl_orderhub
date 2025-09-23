from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
from django.conf import settings


class UTF8EmailBackend(SMTPEmailBackend):
    """
    Кастомный SMTP backend с правильной обработкой UTF-8 кодировки
    """
    
    def _send(self, email_message):
        """Отправка письма с правильной кодировкой"""
        try:
            # Устанавливаем кодировку для письма
            email_message.encoding = 'utf-8'
            
            # Устанавливаем Content-Type для HTML писем
            if hasattr(email_message, 'content_subtype') and email_message.content_subtype == 'html':
                email_message.content_subtype = 'html'
            
            # Добавляем заголовки для правильной кодировки
            email_message.extra_headers = email_message.extra_headers or {}
            email_message.extra_headers['Content-Type'] = 'text/html; charset=UTF-8'
            email_message.extra_headers['Content-Transfer-Encoding'] = '8bit'
            
            # Вызываем родительский метод
            return super()._send(email_message)
            
        except Exception as e:
            # Логируем ошибку
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка отправки email: {str(e)}")
            raise
