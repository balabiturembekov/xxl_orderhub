import os
from django.core.management.base import BaseCommand
from django.db import transaction
from orders.models import Country, Factory


class Command(BaseCommand):
    help = 'Очистка только справочных данных (страны и фабрики) без удаления заказов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительная очистка без подтверждения',
        )

    def handle(self, *args, **options):
        force = options['force']
        
        # Проверяем, есть ли заказы
        from orders.models import Order
        orders_count = Order.objects.count()
        
        if orders_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⚠️ Найдено {orders_count} заказов! Очистка справочных данных может нарушить связи.'
                )
            )
            
            if not force:
                self.stdout.write(
                    self.style.ERROR(
                        '❌ Используйте --force для принудительной очистки.'
                    )
                )
                return
        
        # Очищаем справочные данные
        self.stdout.write('Очистка справочных данных...')
        
        with transaction.atomic():
            factories_count = Factory.objects.count()
            countries_count = Country.objects.count()
            
            Factory.objects.all().delete()
            Country.objects.all().delete()
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Очищено {factories_count} фабрик и {countries_count} стран'
                )
            )
        
        self.stdout.write(
            self.style.SUCCESS('✅ Справочные данные очищены!')
        )
