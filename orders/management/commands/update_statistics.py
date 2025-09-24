from django.core.management.base import BaseCommand
from django.core.cache import cache
from orders.models import Order, Factory, Country


class Command(BaseCommand):
    """
    Команда для обновления статистики системы.
    
    Очищает кэш статистики и принудительно обновляет данные.
    Полезно для администраторов, когда нужно обновить статистику
    без ожидания истечения кэша.
    """
    
    help = 'Обновляет статистику системы и очищает кэш'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--show',
            action='store_true',
            help='Показать текущую статистику без обновления кэша',
        )
        parser.add_argument(
            '--force',
            action='store_true',
            help='Принудительно обновить кэш',
        )
    
    def handle(self, *args, **options):
        if options['show']:
            self.show_statistics()
        elif options['force']:
            self.force_update_statistics()
        else:
            self.update_statistics()
    
    def show_statistics(self):
        """Показать текущую статистику."""
        self.stdout.write(
            self.style.SUCCESS('📊 Текущая статистика системы:')
        )
        
        stats = self._get_fresh_statistics()
        
        self.stdout.write(f"  📦 Всего заказов: {stats['total_orders']}")
        self.stdout.write(f"  🏭 Всего фабрик: {stats['total_factories']}")
        self.stdout.write(f"  🌍 Всего стран: {stats['total_countries']}")
        self.stdout.write(f"  👥 Активных пользователей: {stats['active_users']}")
        
        # Проверяем кэш
        cached_stats = cache.get('public_statistics')
        if cached_stats:
            self.stdout.write(
                self.style.WARNING('\n💾 Статистика кэширована')
            )
        else:
            self.stdout.write(
                self.style.WARNING('\n💾 Кэш пуст')
            )
    
    def update_statistics(self):
        """Обновить статистику (очистить кэш)."""
        self.stdout.write(
            self.style.SUCCESS('🔄 Обновление статистики системы...')
        )
        
        # Очищаем кэш
        cache.delete('public_statistics')
        
        # Получаем свежие данные
        stats = self._get_fresh_statistics()
        
        self.stdout.write(
            self.style.SUCCESS('✅ Статистика обновлена!')
        )
        self.stdout.write(f"  📦 Всего заказов: {stats['total_orders']}")
        self.stdout.write(f"  🏭 Всего фабрик: {stats['total_factories']}")
        self.stdout.write(f"  🌍 Всего стран: {stats['total_countries']}")
        self.stdout.write(f"  👥 Активных пользователей: {stats['active_users']}")
        
        self.stdout.write(
            self.style.SUCCESS('\n💡 Кэш очищен. Статистика будет обновлена при следующем запросе.')
        )
    
    def force_update_statistics(self):
        """Принудительно обновить кэш статистики."""
        self.stdout.write(
            self.style.SUCCESS('🚀 Принудительное обновление статистики...')
        )
        
        # Получаем свежие данные
        stats = self._get_fresh_statistics()
        
        # Принудительно обновляем кэш
        cache.set('public_statistics', stats, 600)  # 10 минут
        
        self.stdout.write(
            self.style.SUCCESS('✅ Статистика принудительно обновлена!')
        )
        self.stdout.write(f"  📦 Всего заказов: {stats['total_orders']}")
        self.stdout.write(f"  🏭 Всего фабрик: {stats['total_factories']}")
        self.stdout.write(f"  🌍 Всего стран: {stats['total_countries']}")
        self.stdout.write(f"  👥 Активных пользователей: {stats['active_users']}")
        
        self.stdout.write(
            self.style.SUCCESS('\n💾 Кэш обновлен и будет действителен 10 минут.')
        )
    
    def _get_fresh_statistics(self):
        """Получить свежую статистику из базы данных."""
        return {
            'total_orders': Order.objects.count(),
            'total_factories': Factory.objects.count(),
            'total_countries': Country.objects.count(),
            'active_users': Order.objects.values('employee').distinct().count(),
        }
