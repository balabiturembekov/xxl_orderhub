"""
Утилиты для работы с кэшем
"""
from django.core.cache import cache
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Order, Factory, Country, Notification


def clear_user_cache(user_id):
    """Очистка кэша пользователя"""
    cache_keys = [
        f'user_stats_{user_id}',
        f'analytics_{user_id}_*',  # Все аналитические данные пользователя
        f'unread_notifications_{user_id}',
    ]
    
    for key in cache_keys:
        if '*' in key:
            # Для ключей с wildcard нужно использовать более сложную логику
            # В реальном проекте можно использовать Redis SCAN
            pass
        else:
            cache.delete(key)


def clear_factories_cache():
    """Очистка кэша фабрик"""
    cache_keys = [
        'active_factories',
        'factories_country_*',  # Все фабрики по странам
    ]
    
    for key in cache_keys:
        if '*' in key:
            # Для ключей с wildcard нужно использовать более сложную логику
            pass
        else:
            cache.delete(key)


@receiver(post_save, sender=Order)
def clear_order_cache(sender, instance, **kwargs):
    """Очистка кэша при изменении заказа"""
    clear_user_cache(instance.employee.id)


@receiver(post_delete, sender=Order)
def clear_order_delete_cache(sender, instance, **kwargs):
    """Очистка кэша при удалении заказа"""
    clear_user_cache(instance.employee.id)


@receiver(post_save, sender=Factory)
def clear_factory_cache(sender, instance, **kwargs):
    """Очистка кэша при изменении фабрики"""
    clear_factories_cache()


@receiver(post_delete, sender=Factory)
def clear_factory_delete_cache(sender, instance, **kwargs):
    """Очистка кэша при удалении фабрики"""
    clear_factories_cache()


@receiver(post_save, sender=Country)
def clear_country_cache(sender, instance, **kwargs):
    """Очистка кэша при изменении страны"""
    clear_factories_cache()


@receiver(post_delete, sender=Country)
def clear_country_delete_cache(sender, instance, **kwargs):
    """Очистка кэша при удалении страны"""
    clear_factories_cache()


@receiver(post_save, sender=Notification)
def clear_notification_cache(sender, instance, **kwargs):
    """Очистка кэша при изменении уведомления"""
    clear_user_cache(instance.user.id)


@receiver(post_delete, sender=Notification)
def clear_notification_delete_cache(sender, instance, **kwargs):
    """Очистка кэша при удалении уведомления"""
    clear_user_cache(instance.user.id)
