from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask
from django.utils import timezone


class Command(BaseCommand):
    help = 'Show Celery Beat status and task information'

    def handle(self, *args, **kwargs):
        self.stdout.write('=== Celery Beat Status ===\n')
        
        # Показываем все периодические задачи
        tasks = PeriodicTask.objects.all()
        
        if not tasks.exists():
            self.stdout.write(self.style.WARNING('No periodic tasks found'))
            return
        
        for task in tasks:
            status = '✓ Enabled' if task.enabled else '✗ Disabled'
            color = self.style.SUCCESS if task.enabled else self.style.ERROR
            
            self.stdout.write(f'Task: {task.name}')
            self.stdout.write(f'  Status: {color(status)}')
            self.stdout.write(f'  Task: {task.task}')
            self.stdout.write(f'  Description: {task.description}')
            
            if task.crontab:
                self.stdout.write(f'  Schedule: {task.crontab}')
            elif task.interval:
                self.stdout.write(f'  Interval: {task.interval}')
            
            if task.last_run_at:
                self.stdout.write(f'  Last run: {task.last_run_at}')
            else:
                self.stdout.write('  Last run: Never')
            
            if task.total_run_count:
                self.stdout.write(f'  Total runs: {task.total_run_count}')
            
            self.stdout.write('')
        
        # Показываем статистику
        enabled_count = tasks.filter(enabled=True).count()
        total_count = tasks.count()
        
        self.stdout.write(f'Summary: {enabled_count}/{total_count} tasks enabled')
        
        # Показываем следующее выполнение
        next_run_tasks = tasks.filter(enabled=True).exclude(last_run_at__isnull=True)
        if next_run_tasks.exists():
            self.stdout.write('\nNext scheduled runs:')
            for task in next_run_tasks[:5]:  # Показываем только первые 5
                if task.crontab:
                    next_run = task.crontab.schedule.next_run_at(timezone.now())
                    self.stdout.write(f'  {task.name}: {next_run}')
