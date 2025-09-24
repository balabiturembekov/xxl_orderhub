# Generated manually to fix migration conflicts

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0003_alter_order_excel_file_alter_order_invoice_file'),
    ]

    operations = [
        # Помечаем существующие таблицы как уже примененные
        migrations.RunSQL(
            "SELECT 1;",  # Ничего не делаем, просто помечаем как выполненное
            reverse_sql="SELECT 1;",
            state_operations=[
                # Создаем состояние для OrderAuditLog
                migrations.CreateModel(
                    name='OrderAuditLog',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('action', models.CharField(choices=[('created', 'Создан'), ('updated', 'Обновлен'), ('status_changed', 'Изменен статус'), ('file_uploaded', 'Загружен файл'), ('file_downloaded', 'Скачан файл'), ('sent', 'Отправлен'), ('completed', 'Завершен'), ('cancelled', 'Отменен'), ('deleted', 'Удален')], max_length=20, verbose_name='Действие')),
                        ('old_value', models.TextField(blank=True, verbose_name='Старое значение')),
                        ('new_value', models.TextField(blank=True, verbose_name='Новое значение')),
                        ('field_name', models.CharField(blank=True, max_length=50, verbose_name='Поле')),
                        ('ip_address', models.GenericIPAddressField(blank=True, null=True, verbose_name='IP адрес')),
                        ('user_agent', models.TextField(blank=True, verbose_name='User Agent')),
                        ('comments', models.TextField(blank=True, verbose_name='Комментарии')),
                        ('timestamp', models.DateTimeField(auto_now_add=True, verbose_name='Время')),
                        ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='orders.order', verbose_name='Заказ')),
                        ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
                    ],
                    options={
                        'verbose_name': 'Запись аудита',
                        'verbose_name_plural': 'Журнал аудита',
                        'ordering': ['-timestamp'],
                    },
                ),
                # Создаем состояние для OrderConfirmation
                migrations.CreateModel(
                    name='OrderConfirmation',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('action', models.CharField(choices=[('send_order', 'Отправка заказа'), ('upload_invoice', 'Загрузка инвойса'), ('complete_order', 'Завершение заказа'), ('cancel_order', 'Отмена заказа'), ('delete_order', 'Удаление заказа')], max_length=20, verbose_name='Действие')),
                        ('status', models.CharField(choices=[('pending', 'Ожидает подтверждения'), ('confirmed', 'Подтверждено'), ('rejected', 'Отклонено'), ('expired', 'Истекло')], default='pending', max_length=20, verbose_name='Статус')),
                        ('confirmation_data', models.JSONField(default=dict, verbose_name='Данные подтверждения')),
                        ('comments', models.TextField(blank=True, verbose_name='Комментарии')),
                        ('rejection_reason', models.TextField(blank=True, verbose_name='Причина отклонения')),
                        ('requested_at', models.DateTimeField(auto_now_add=True, verbose_name='Запрошено')),
                        ('confirmed_at', models.DateTimeField(blank=True, null=True, verbose_name='Подтверждено')),
                        ('expires_at', models.DateTimeField(help_text='Автоматически устанавливается при создании', verbose_name='Истекает')),
                        ('confirmed_by', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='confirmed_actions', to=settings.AUTH_USER_MODEL, verbose_name='Подтвердил')),
                        ('order', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='orders.order', verbose_name='Заказ')),
                        ('requested_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL, verbose_name='Запросил')),
                    ],
                    options={
                        'verbose_name': 'Подтверждение операции',
                        'verbose_name_plural': 'Подтверждения операций',
                        'ordering': ['-requested_at'],
                    },
                ),
                # Создаем состояние для UserProfile
                migrations.CreateModel(
                    name='UserProfile',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('first_name', models.CharField(blank=True, max_length=50, verbose_name='Имя')),
                        ('last_name', models.CharField(blank=True, max_length=50, verbose_name='Фамилия')),
                        ('phone', models.CharField(blank=True, max_length=20, verbose_name='Телефон')),
                        ('department', models.CharField(blank=True, max_length=100, verbose_name='Отдел')),
                        ('position', models.CharField(blank=True, max_length=100, verbose_name='Должность')),
                        ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Дата создания профиля')),
                        ('updated_at', models.DateTimeField(auto_now=True, verbose_name='Дата обновления профиля')),
                        ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='profile', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
                    ],
                    options={
                        'verbose_name': 'Профиль пользователя',
                        'verbose_name_plural': 'Профили пользователей',
                        'ordering': ['user__username'],
                    },
                ),
            ]
        ),
    ]
