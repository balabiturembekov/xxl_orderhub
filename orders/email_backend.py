from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend
from django.conf import settings
from email.header import Header


class UTF8EmailBackend(SMTPEmailBackend):
    """
    Кастомный SMTP backend с правильной обработкой UTF-8 кодировки
    
    Гарантирует правильное отображение кириллицы и других не-ASCII символов
    во всех почтовых клиентах.
    """
    
    def _send(self, email_message):
        """Отправка письма с правильной кодировкой"""
        try:
            # Устанавливаем кодировку для письма
            email_message.encoding = 'utf-8'
            
            # Правильно кодируем subject для не-ASCII символов
            if hasattr(email_message, 'subject') and email_message.subject:
                try:
                    # Проверяем, есть ли не-ASCII символы
                    subject_str = str(email_message.subject)
                    # Если subject уже закодирован через Header, оставляем как есть
                    if not (subject_str.startswith('=?') and '?=' in subject_str):
                        # Кодируем subject через Header для правильной обработки не-ASCII
                        try:
                            subject_bytes = subject_str.encode('ascii')
                            # Если успешно закодировалось в ASCII, значит только ASCII символы
                        except UnicodeEncodeError:
                            # Есть не-ASCII символы, кодируем через Header
                            email_message.subject = str(Header(subject_str, 'utf-8'))
                except (AttributeError, UnicodeError):
                    # В случае ошибки оставляем как есть
                    pass
            
            # Устанавливаем Content-Type для HTML писем
            if hasattr(email_message, 'content_subtype') and email_message.content_subtype == 'html':
                email_message.content_subtype = 'html'
            
            # Добавляем заголовки для правильной кодировки
            # Это критично для старых почтовых клиентов
            email_message.extra_headers = email_message.extra_headers or {}
            
            # Устанавливаем Content-Type в зависимости от типа контента
            if hasattr(email_message, 'content_subtype') and email_message.content_subtype == 'html':
                email_message.extra_headers['Content-Type'] = 'text/html; charset=UTF-8'
            else:
                email_message.extra_headers['Content-Type'] = 'text/plain; charset=UTF-8'
            
            email_message.extra_headers['Content-Transfer-Encoding'] = '8bit'
            email_message.extra_headers['MIME-Version'] = '1.0'
            
            # Вызываем родительский метод
            return super()._send(email_message)
            
        except Exception as e:
            # Логируем ошибку
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка отправки email: {str(e)}")
            raise
