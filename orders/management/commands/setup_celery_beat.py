from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, CrontabSchedule, IntervalSchedule
from django.utils import timezone


class Command(BaseCommand):
    help = 'Setup Celery Beat periodic tasks'

    def handle(self, *args, **kwargs):
        self.stdout.write('Setting up Celery Beat periodic tasks...')
        
        # 1. Проверка просроченных заказов - каждый день в 9:00
        schedule, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='9',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        
        task, created = PeriodicTask.objects.get_or_create(
            name='Check Overdue Orders',
            defaults={
                'task': 'orders.tasks.check_overdue_orders',
                'crontab': schedule,
                'enabled': True,
                'description': 'Проверка просроченных заказов и отправка напоминаний',
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created task: Check Overdue Orders'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Task already exists: Check Overdue Orders'))
        
        # 2. Создание шаблонов уведомлений - один раз при запуске
        schedule_once, created = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.DAYS,
        )
        
        task_once, created = PeriodicTask.objects.get_or_create(
            name='Create Default Notification Templates',
            defaults={
                'task': 'orders.tasks.create_default_notification_templates',
                'interval': schedule_once,
                'enabled': True,
                'description': 'Создание шаблонов уведомлений по умолчанию',
                'one_off': True,  # Выполнить только один раз
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created task: Create Default Notification Templates'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Task already exists: Create Default Notification Templates'))
        
        # 3. Очистка старых уведомлений - каждую неделю в воскресенье в 2:00
        schedule_cleanup, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='2',
            day_of_week='0',  # Воскресенье
            day_of_month='*',
            month_of_year='*',
        )
        
        task_cleanup, created = PeriodicTask.objects.get_or_create(
            name='Cleanup Old Notifications',
            defaults={
                'task': 'orders.tasks.cleanup_old_notifications',
                'crontab': schedule_cleanup,
                'enabled': True,
                'description': 'Очистка старых уведомлений (старше 30 дней)',
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created task: Cleanup Old Notifications'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Task already exists: Cleanup Old Notifications'))
        
        # 4. Статистика системы - каждый день в 23:00
        schedule_stats, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='23',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        
        task_stats, created = PeriodicTask.objects.get_or_create(
            name='Generate System Statistics',
            defaults={
                'task': 'orders.tasks.generate_system_statistics',
                'crontab': schedule_stats,
                'enabled': True,
                'description': 'Генерация ежедневной статистики системы',
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created task: Generate System Statistics'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Task already exists: Generate System Statistics'))
        
        # 5. Проверка просроченных платежей - каждый день в 10:00
        schedule_payments, created = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='10',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )
        
        task_payments, created = PeriodicTask.objects.get_or_create(
            name='Check Overdue Payments',
            defaults={
                'task': 'orders.tasks.check_overdue_payments',
                'crontab': schedule_payments,
                'enabled': True,
                'description': 'Проверка просроченных платежей и отправка уведомлений',
            }
        )
        
        if created:
            self.stdout.write(self.style.SUCCESS('✓ Created task: Check Overdue Payments'))
        else:
            self.stdout.write(self.style.WARNING('⚠ Task already exists: Check Overdue Payments'))
        
        self.stdout.write(self.style.SUCCESS('Successfully set up Celery Beat periodic tasks!'))
        
        # Показываем список всех задач
        self.stdout.write('\nCurrent periodic tasks:')
        for task in PeriodicTask.objects.all():
            status = '✓ Enabled' if task.enabled else '✗ Disabled'
            self.stdout.write(f'  - {task.name}: {status}')
