from django.core.management.base import BaseCommand
from orders.models import Country, Factory, Order


class Command(BaseCommand):
    help = 'Проверка целостности данных в системе'

    def handle(self, *args, **options):
        self.stdout.write('🔍 Проверка целостности данных...')
        
        # Подсчитываем данные
        countries_count = Country.objects.count()
        factories_count = Factory.objects.count()
        orders_count = Order.objects.count()
        
        self.stdout.write(f'📊 Статистика данных:')
        self.stdout.write(f'   • Стран: {countries_count}')
        self.stdout.write(f'   • Фабрик: {factories_count}')
        self.stdout.write(f'   • Заказов: {orders_count}')
        
        # Проверяем заказы без фабрик
        orphaned_orders = Order.objects.filter(factory__isnull=True).count()
        if orphaned_orders > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ Найдено {orphaned_orders} заказов без фабрик!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Все заказы имеют связанные фабрики')
            )
        
        # Проверяем фабрики без стран
        orphaned_factories = Factory.objects.filter(country__isnull=True).count()
        if orphaned_factories > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ Найдено {orphaned_factories} фабрик без стран!')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Все фабрики имеют связанные страны')
            )
        
        # Проверяем дубликаты фабрик
        from django.db.models import Count
        duplicate_factories = Factory.objects.values('name').annotate(
            count=Count('name')
        ).filter(count__gt=1)
        
        if duplicate_factories.exists():
            self.stdout.write(
                self.style.WARNING(f'⚠️ Найдено дубликаты фабрик:')
            )
            for factory in duplicate_factories:
                self.stdout.write(f'   • {factory["name"]}: {factory["count"]} раз')
        else:
            self.stdout.write(
                self.style.SUCCESS('✅ Дубликатов фабрик не найдено')
            )
        
        self.stdout.write(
            self.style.SUCCESS('✅ Проверка целостности завершена!')
        )
