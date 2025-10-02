"""
Management команда для проверки настроек email.
"""

from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
import os


class Command(BaseCommand):
    help = 'Проверяет текущие настройки email и отправляет тестовое письмо'

    def add_arguments(self, parser):
        parser.add_argument(
            '--test-email',
            type=str,
            help='Email адрес для отправки тестового письма',
        )
        parser.add_argument(
            '--send-test',
            action='store_true',
            help='Отправить тестовое письмо',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=== ПРОВЕРКА НАСТРОЕК EMAIL ==='))
        
        # Показываем текущие настройки
        self.show_email_settings()
        
        # Показываем переменные окружения
        self.show_env_variables()
        
        # Отправляем тестовое письмо если запрошено
        if options.get('send_test') and options.get('test_email'):
            self.send_test_email(options['test_email'])
    
    def show_email_settings(self):
        """Показывает текущие настройки Django email"""
        self.stdout.write('\n📧 Django Email Settings:')
        self.stdout.write(f'  EMAIL_BACKEND: {settings.EMAIL_BACKEND}')
        self.stdout.write(f'  EMAIL_HOST: {settings.EMAIL_HOST}')
        self.stdout.write(f'  EMAIL_PORT: {settings.EMAIL_PORT}')
        self.stdout.write(f'  EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}')
        self.stdout.write(f'  EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}')
        self.stdout.write(f'  EMAIL_HOST_PASSWORD: {"*" * len(settings.EMAIL_HOST_PASSWORD) if settings.EMAIL_HOST_PASSWORD else "НЕ УСТАНОВЛЕН"}')
        self.stdout.write(f'  DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}')
        
        if hasattr(settings, 'EMAIL_CHARSET'):
            self.stdout.write(f'  EMAIL_CHARSET: {settings.EMAIL_CHARSET}')
        if hasattr(settings, 'BASE_URL'):
            self.stdout.write(f'  BASE_URL: {settings.BASE_URL}')
    
    def show_env_variables(self):
        """Показывает переменные окружения связанные с email"""
        self.stdout.write('\n🔧 Environment Variables:')
        
        email_vars = [
            'EMAIL_BACKEND',
            'EMAIL_HOST', 
            'EMAIL_PORT',
            'EMAIL_USE_TLS',
            'EMAIL_HOST_USER',
            'EMAIL_HOST_PASSWORD',
            'DEFAULT_FROM_EMAIL',
            'EMAIL_CHARSET',
            'BASE_URL'
        ]
        
        for var in email_vars:
            value = os.environ.get(var, 'НЕ УСТАНОВЛЕНА')
            if 'PASSWORD' in var and value != 'НЕ УСТАНОВЛЕНА':
                value = '*' * len(value)
            self.stdout.write(f'  {var}: {value}')
    
    def send_test_email(self, email):
        """Отправляет тестовое письмо"""
        self.stdout.write(f'\n📤 Отправка тестового письма на {email}...')
        
        try:
            # Простое тестовое письмо
            send_mail(
                subject='XXL OrderHub - Тест настроек email',
                message=f'''
Тестовое письмо для проверки настроек email.

Настройки:
- EMAIL_BACKEND: {settings.EMAIL_BACKEND}
- EMAIL_HOST: {settings.EMAIL_HOST}
- EMAIL_PORT: {settings.EMAIL_PORT}
- EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}
- EMAIL_HOST_USER: {settings.EMAIL_HOST_USER}
- DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}

Если вы получили это письмо, настройки email работают корректно!
                ''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
                fail_silently=False,
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✅ Тестовое письмо успешно отправлено на {email}')
            )
            
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка отправки письма: {str(e)}')
            )
            
            # Показываем детали ошибки
            import traceback
            self.stdout.write(f'Детали ошибки:\n{traceback.format_exc()}')
    
    def check_email_backend(self):
        """Проверяет кастомный email backend"""
        self.stdout.write('\n🔍 Проверка кастомного email backend:')
        
        try:
            from orders.email_backend import UTF8EmailBackend
            self.stdout.write('  ✅ UTF8EmailBackend найден')
            
            # Проверяем, что backend корректно импортируется
            backend = UTF8EmailBackend()
            self.stdout.write('  ✅ UTF8EmailBackend успешно инициализирован')
            
        except ImportError as e:
            self.stdout.write(f'  ❌ Ошибка импорта UTF8EmailBackend: {e}')
        except Exception as e:
            self.stdout.write(f'  ❌ Ошибка инициализации UTF8EmailBackend: {e}')
