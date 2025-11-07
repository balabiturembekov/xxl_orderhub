# Generated manually to create missing tables

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('orders', '0010_ordercbm'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Используем RunSQL для создания таблиц с проверкой существования
        # Это предотвращает ошибку, если таблицы уже существуют (созданные вручную ранее)
        migrations.RunSQL(
            sql="""
            CREATE TABLE IF NOT EXISTS orders_orderauditlog (
                id BIGSERIAL PRIMARY KEY,
                action VARCHAR(20) NOT NULL,
                old_value TEXT NOT NULL DEFAULT '',
                new_value TEXT NOT NULL DEFAULT '',
                field_name VARCHAR(50) NOT NULL DEFAULT '',
                ip_address INET,
                user_agent TEXT NOT NULL DEFAULT '',
                comments TEXT NOT NULL DEFAULT '',
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                order_id BIGINT NOT NULL REFERENCES orders_order(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS orders_orderconfirmation (
                id BIGSERIAL PRIMARY KEY,
                action VARCHAR(20) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'pending',
                confirmation_data JSONB NOT NULL DEFAULT '{}',
                comments TEXT NOT NULL DEFAULT '',
                rejection_reason TEXT NOT NULL DEFAULT '',
                requested_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                confirmed_at TIMESTAMP WITH TIME ZONE,
                expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
                order_id BIGINT NOT NULL REFERENCES orders_order(id) ON DELETE CASCADE,
                requested_by_id INTEGER NOT NULL REFERENCES auth_user(id) ON DELETE CASCADE,
                confirmed_by_id INTEGER REFERENCES auth_user(id) ON DELETE CASCADE
            );
            CREATE TABLE IF NOT EXISTS orders_userprofile (
                id BIGSERIAL PRIMARY KEY,
                first_name VARCHAR(50) NOT NULL DEFAULT '',
                last_name VARCHAR(50) NOT NULL DEFAULT '',
                phone VARCHAR(20) NOT NULL DEFAULT '',
                department VARCHAR(100) NOT NULL DEFAULT '',
                position VARCHAR(100) NOT NULL DEFAULT '',
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                user_id INTEGER NOT NULL UNIQUE REFERENCES auth_user(id) ON DELETE CASCADE
            );
            """,
            reverse_sql="""
            DROP TABLE IF EXISTS orders_userprofile;
            DROP TABLE IF EXISTS orders_orderconfirmation;
            DROP TABLE IF EXISTS orders_orderauditlog;
            """,
            state_operations=[
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
                        ('expires_at', models.DateTimeField(verbose_name='Истекает', help_text='Автоматически устанавливается при создании')),
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
