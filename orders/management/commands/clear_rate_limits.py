"""
Management команда для очистки rate limiting кэша.
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache


class Command(BaseCommand):
    help = 'Очищает кэш rate limiting для всех IP адресов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--ip',
            type=str,
            help='Очистить rate limiting для конкретного IP адреса',
        )
        parser.add_argument(
            '--action',
            type=str,
            choices=['file_upload', 'api', 'all'],
            default='all',
            help='Тип действия для очистки (по умолчанию: all)',
        )

    def handle(self, *args, **options):
        ip = options.get('ip')
        action = options.get('action')
        
        if ip:
            # Очищаем для конкретного IP
            if action == 'all':
                actions = ['file_upload', 'api']
            else:
                actions = [action]
            
            cleared_count = 0
            for act in actions:
                key = f"rate_limit:{act}:{ip}"
                if cache.delete(key):
                    cleared_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(f'Очищен rate limiting для IP {ip}, действие: {act}')
                    )
            
            if cleared_count == 0:
                self.stdout.write(
                    self.style.WARNING(f'Rate limiting для IP {ip} не найден в кэше')
                )
        else:
            # Очищаем все rate limiting записи
            if action == 'all':
                # Очищаем все ключи rate limiting
                keys_to_delete = []
                for key in cache._cache.keys():
                    if key.startswith('rate_limit:'):
                        keys_to_delete.append(key)
                
                cleared_count = 0
                for key in keys_to_delete:
                    if cache.delete(key):
                        cleared_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(f'Очищено {cleared_count} записей rate limiting')
                )
            else:
                # Очищаем только определенный тип действия
                keys_to_delete = []
                for key in cache._cache.keys():
                    if key.startswith(f'rate_limit:{action}:'):
                        keys_to_delete.append(key)
                
                cleared_count = 0
                for key in keys_to_delete:
                    if cache.delete(key):
                        cleared_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(f'Очищено {cleared_count} записей rate limiting для действия: {action}')
                )
