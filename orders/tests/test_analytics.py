from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from orders.models import Order, Country, Factory
from orders.analytics import AnalyticsService, get_analytics_data


class AnalyticsTestCase(TestCase):
    def setUp(self):
        """Настройка тестовых данных"""
        # Создаем пользователя
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123'
        )
        
        # Создаем страны и фабрики
        self.country1 = Country.objects.create(name='Германия', code='DE')
        self.country2 = Country.objects.create(name='Италия', code='IT')
        
        self.factory1 = Factory.objects.create(
            name='Berlin Furniture GmbH',
            country=self.country1,
            email='orders@berlin-furniture.de',
            is_active=True
        )
        
        self.factory2 = Factory.objects.create(
            name='Milano Design SRL',
            country=self.country2,
            email='orders@milano-design.it',
            is_active=True
        )
        
        # Создаем тестовые заказы
        now = timezone.now()
        for i in range(10):
            days_ago = i * 2
            created_date = now - timedelta(days=days_ago)
            
            status = 'completed' if i < 5 else 'sent' if i < 8 else 'uploaded'
            factory = self.factory1 if i % 2 == 0 else self.factory2
            
            # Для завершенных заказов убеждаемся, что completed_at > uploaded_at
            completed_at = None
            if status == 'completed':
                completed_at = created_date + timedelta(days=3)
            
            Order.objects.create(
                title=f'Тестовый заказ #{i+1}',
                description=f'Описание тестового заказа #{i+1}',
                factory=factory,
                employee=self.user,
                status=status,
                uploaded_at=created_date,
                sent_at=created_date + timedelta(days=1) if status in ['sent', 'completed'] else None,
                completed_at=completed_at
            )
    
    def test_analytics_service_overview(self):
        """Тест общей статистики"""
        analytics = AnalyticsService(user=self.user)
        overview = analytics.get_orders_overview()
        
        self.assertEqual(overview['total_orders'], 10)
        self.assertEqual(overview['completed'], 5)
        self.assertEqual(overview['sent'], 3)
        self.assertEqual(overview['uploaded'], 2)
    
    def test_analytics_service_factory_stats(self):
        """Тест статистики по фабрикам"""
        analytics = AnalyticsService(user=self.user)
        factory_stats = analytics.get_factory_stats()
        
        self.assertEqual(len(factory_stats), 2)
        
        # Проверяем, что у каждой фабрики есть заказы
        total_orders = sum(stat['total_orders'] for stat in factory_stats)
        self.assertEqual(total_orders, 10)
    
    def test_analytics_service_country_stats(self):
        """Тест статистики по странам"""
        analytics = AnalyticsService(user=self.user)
        country_stats = analytics.get_country_stats()
        
        self.assertEqual(len(country_stats), 2)
        
        # Проверяем, что у каждой страны есть заказы
        total_orders = sum(stat['total_orders'] for stat in country_stats)
        self.assertEqual(total_orders, 10)
    
    def test_analytics_service_kpi_metrics(self):
        """Тест KPI метрик"""
        analytics = AnalyticsService(user=self.user)
        kpi = analytics.get_kpi_metrics()
        
        self.assertEqual(kpi['total_orders'], 10)
        self.assertEqual(kpi['completion_rate'], 50.0)  # 5 из 10 завершено
        self.assertGreater(kpi['avg_processing_time'], 0)
    
    def test_analytics_service_time_series(self):
        """Тест временных рядов"""
        analytics = AnalyticsService(user=self.user)
        time_series = analytics.get_time_series_data()
        
        # Должны быть данные за несколько дней
        self.assertGreater(len(time_series), 0)
        
        # Проверяем структуру данных
        if time_series:
            first_item = time_series[0]
            self.assertIn('period', first_item)
            self.assertIn('total_orders', first_item)
    
    def test_analytics_dashboard_view(self):
        """Тест view дашборда аналитики"""
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('analytics_dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Аналитика и отчеты')
    
    def test_analytics_export_view(self):
        """Тест экспорта аналитики"""
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('analytics_export'), {'type': 'overview'})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 
                        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    
    def test_analytics_api_view(self):
        """Тест API аналитики"""
        client = Client()
        client.force_login(self.user)
        
        response = client.get(reverse('analytics_api'), {'chart_type': 'overview'})
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('overview', data)
        self.assertIn('kpi_metrics', data)
    
    def test_get_analytics_data_function(self):
        """Тест функции get_analytics_data"""
        data = get_analytics_data(user=self.user)
        
        self.assertIn('overview', data)
        self.assertIn('factory_stats', data)
        self.assertIn('country_stats', data)
        self.assertIn('kpi_metrics', data)
        self.assertIn('time_series', data)
        self.assertIn('date_range', data)
        
        # Проверяем структуру данных
        self.assertEqual(data['overview']['total_orders'], 10)
        self.assertEqual(data['kpi_metrics']['total_orders'], 10)
