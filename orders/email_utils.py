"""
Утилиты для работы с многоязычными email шаблонами
"""

# Маппинг кодов стран на языки
COUNTRY_LANGUAGE_MAP = {
    'IT': 'it',  # Италия - итальянский
    'TR': 'tr',  # Турция - турецкий
    'PL': 'pl',  # Польша - польский
    'CZ': 'cz',  # Чехия - чешский
    'CN': 'cn',  # Китай - китайский
    'LT': 'lt',  # Литва - литовский
    'CH': 'ch',  # Швейцария - немецкий
}

# Маппинг языков на названия языков
LANGUAGE_NAMES = {
    'ru': 'Русский',
    'it': 'Italiano',
    'tr': 'Türkçe',
    'pl': 'Polski',
    'cz': 'Čeština',
    'cn': '中文',
    'lt': 'Lietuvių',
    'ch': 'Deutsch',
}

# Маппинг языков на заголовки писем
EMAIL_SUBJECTS = {
    'ru': 'Заказ на производство',
    'it': 'Ordine di produzione',
    'tr': 'Üretim siparişi',
    'pl': 'Zamówienie produkcyjne',
    'cz': 'Výrobní objednávka',
    'cn': '生产订单',
    'lt': 'Gamybos užsakymas',
    'ch': 'Produktionsauftrag',
}


def get_language_by_country_code(country_code):
    """
    Получить язык по коду страны
    
    Args:
        country_code (str): Код страны (например, 'IT', 'TR')
    
    Returns:
        str: Код языка (например, 'it', 'tr') или 'ru' по умолчанию
    """
    return COUNTRY_LANGUAGE_MAP.get(country_code.upper(), 'ru')


def get_language_name(language_code):
    """
    Получить название языка по коду
    
    Args:
        language_code (str): Код языка
    
    Returns:
        str: Название языка
    """
    return LANGUAGE_NAMES.get(language_code, 'Русский')


def get_email_subject(language_code):
    """
    Получить заголовок письма на соответствующем языке
    
    Args:
        language_code (str): Код языка
    
    Returns:
        str: Заголовок письма
    """
    return EMAIL_SUBJECTS.get(language_code, 'Заказ на производство')


def get_email_template_paths(language_code):
    """
    Получить пути к шаблонам письма для указанного языка
    
    Args:
        language_code (str): Код языка
    
    Returns:
        tuple: (html_template_path, txt_template_path)
    """
    if language_code not in COUNTRY_LANGUAGE_MAP.values():
        language_code = 'ru'  # Fallback to Russian
    
    html_path = f'emails/factory_orders/{language_code}.html'
    txt_path = f'emails/factory_orders/{language_code}.txt'
    
    return html_path, txt_path


def get_email_template_from_db(template_type, language_code):
    """
    Получить email шаблон из базы данных
    
    Args:
        template_type (str): Тип шаблона ('order_confirmation', 'order_notification', etc.)
        language_code (str): Код языка
    
    Returns:
        EmailTemplate: Шаблон из БД или None если не найден
    """
    from .models import EmailTemplate
    
    try:
        # Сначала ищем активный шаблон по умолчанию для данного типа и языка
        template = EmailTemplate.objects.get(
            template_type=template_type,
            language=language_code,
            is_active=True,
            is_default=True
        )
        return template
    except EmailTemplate.DoesNotExist:
        try:
            # Если не найден по умолчанию, ищем любой активный шаблон
            template = EmailTemplate.objects.filter(
                template_type=template_type,
                language=language_code,
                is_active=True
            ).first()
            return template
        except EmailTemplate.DoesNotExist:
            # Если не найден для данного языка, ищем русский как fallback
            try:
                template = EmailTemplate.objects.get(
                    template_type=template_type,
                    language='ru',
                    is_active=True,
                    is_default=True
                )
                return template
            except EmailTemplate.DoesNotExist:
                return None


def get_supported_languages():
    """
    Получить список поддерживаемых языков
    
    Returns:
        list: Список кортежей (код_языка, название_языка)
    """
    return [(code, name) for code, name in LANGUAGE_NAMES.items()]
