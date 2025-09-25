"""
Константы для модуля orders.

Этот файл содержит все константы, используемые в модуле orders,
для устранения магических чисел и улучшения читаемости кода.
"""

# ============================================================================
# КОНСТАНТЫ ДЛЯ МОДЕЛЕЙ
# ============================================================================

class ModelConstants:
    """Константы для моделей Django"""
    
    # Длины полей
    MAX_TITLE_LENGTH = 200
    MAX_DESCRIPTION_LENGTH = 1000
    MAX_COMMENT_LENGTH = 500
    MAX_PHONE_LENGTH = 20
    MAX_DEPARTMENT_LENGTH = 100
    MAX_POSITION_LENGTH = 100
    MAX_FACTORY_NAME_LENGTH = 200
    MAX_COUNTRY_NAME_LENGTH = 100
    MAX_COUNTRY_CODE_LENGTH = 3
    MAX_NOTIFICATION_TITLE_LENGTH = 200
    MAX_NOTIFICATION_MESSAGE_LENGTH = 1000
    MAX_INVOICE_NUMBER_LENGTH = 100
    
    # Коды стран
    DEFAULT_COUNTRY_CODE = 'DE'
    
    # Статусы заказов
    ORDER_STATUS_UPLOADED = 'uploaded'
    ORDER_STATUS_SENT = 'sent'
    ORDER_STATUS_INVOICE_RECEIVED = 'invoice_received'
    ORDER_STATUS_COMPLETED = 'completed'
    ORDER_STATUS_CANCELLED = 'cancelled'
    
    # Статусы подтверждений
    CONFIRMATION_STATUS_PENDING = 'pending'
    CONFIRMATION_STATUS_APPROVED = 'approved'
    CONFIRMATION_STATUS_REJECTED = 'rejected'
    CONFIRMATION_STATUS_EXPIRED = 'expired'
    
    # Статусы инвойсов
    INVOICE_STATUS_PENDING = 'pending'
    INVOICE_STATUS_PAID = 'paid'
    INVOICE_STATUS_OVERDUE = 'overdue'
    INVOICE_STATUS_CANCELLED = 'cancelled'

# ============================================================================
# КОНСТАНТЫ ДЛЯ VIEWS
# ============================================================================

class ViewConstants:
    """Константы для Django views"""
    
    # Пагинация
    DEFAULT_PAGE_SIZE = 20
    MAX_PAGE_SIZE = 100
    MIN_PAGE_SIZE = 5
    
    # Поиск
    SEARCH_MIN_LENGTH = 2
    SEARCH_MAX_LENGTH = 100
    
    # Фильтрация
    MAX_FILTER_ITEMS = 50
    
    # Экспорт
    MAX_EXPORT_ITEMS = 1000

# ============================================================================
# КОНСТАНТЫ ДЛЯ ФАЙЛОВ
# ============================================================================

class FileConstants:
    """Константы для работы с файлами"""
    
    # Размеры файлов (в байтах)
    MAX_EXCEL_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    MAX_PDF_SIZE = 2 * 1024 * 1024 * 1024    # 2GB
    MAX_IMAGE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
    
    # Размеры файлов (в MB для отображения)
    MAX_EXCEL_SIZE_MB = 2048
    MAX_PDF_SIZE_MB = 2048
    MAX_IMAGE_SIZE_MB = 2048
    
    # Разрешенные расширения
    ALLOWED_EXCEL_EXTENSIONS = ['xlsx', 'xls']
    ALLOWED_PDF_EXTENSIONS = ['pdf']
    ALLOWED_IMAGE_EXTENSIONS = ['jpg', 'jpeg', 'png', 'gif']
    
    # Пути для загрузки
    EXCEL_UPLOAD_PATH = 'orders/excel/'
    PDF_UPLOAD_PATH = 'orders/invoices/'
    IMAGE_UPLOAD_PATH = 'orders/images/'
    
    # MIME типы
    EXCEL_MIME_TYPES = [
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'application/vnd.ms-excel'
    ]
    PDF_MIME_TYPES = ['application/pdf']
    IMAGE_MIME_TYPES = ['image/jpeg', 'image/png', 'image/gif']

# ============================================================================
# КОНСТАНТЫ ДЛЯ ВРЕМЕНИ
# ============================================================================

class TimeConstants:
    """Константы для работы с временем"""
    
    # Частота напоминаний (в днях)
    DEFAULT_REMINDER_FREQUENCY = 7
    MIN_REMINDER_FREQUENCY = 1
    MAX_REMINDER_FREQUENCY = 30
    
    # Время жизни подтверждений (в часах)
    CONFIRMATION_EXPIRATION_HOURS = 24
    CONFIRMATION_EXPIRATION_HOURS_INVOICE = 48  # 2 дня для инвойса
    CONFIRMATION_EXPIRATION_HOURS_SEND = 72    # 3 дня для отправки
    
    # Минимальное время для напоминаний (в днях)
    MIN_REMINDER_DAYS = 1
    
    # Время для статистики (в днях)
    STATS_DAYS = 3
    
    # Время хранения данных (в днях)
    METRICS_RETENTION_DAYS = 30
    LOG_RETENTION_DAYS = 7

# ============================================================================
# КОНСТАНТЫ ДЛЯ УВЕДОМЛЕНИЙ
# ============================================================================

class NotificationConstants:
    """Константы для системы уведомлений"""
    
    # Типы уведомлений
    NOTIFICATION_TYPE_ORDER_UPLOADED = 'order_uploaded'
    NOTIFICATION_TYPE_ORDER_SENT = 'order_sent'
    NOTIFICATION_TYPE_INVOICE_RECEIVED = 'invoice_received'
    NOTIFICATION_TYPE_ORDER_COMPLETED = 'order_completed'
    NOTIFICATION_TYPE_UPLOADED_REMINDER = 'uploaded_reminder'
    NOTIFICATION_TYPE_SENT_REMINDER = 'sent_reminder'
    NOTIFICATION_TYPE_PAYMENT_OVERDUE = 'payment_overdue'
    
    # Настройки email
    EMAIL_SUBJECT_PREFIX = '[XXL OrderHub]'
    EMAIL_FROM_NAME = 'XXL OrderHub System'

# ============================================================================
# КОНСТАНТЫ ДЛЯ АНАЛИТИКИ
# ============================================================================

class AnalyticsConstants:
    """Константы для аналитики"""
    
    # Периоды для аналитики (в днях)
    DEFAULT_ANALYTICS_PERIOD = 30
    MIN_ANALYTICS_PERIOD = 7
    MAX_ANALYTICS_PERIOD = 365
    
    # Кэширование
    ANALYTICS_CACHE_TIMEOUT = 15 * 60  # 15 минут
    PUBLIC_STATS_CACHE_TIMEOUT = 10 * 60  # 10 минут
    
    # Лимиты для отображения
    MAX_TOP_FACTORIES = 10
    MAX_TOP_COUNTRIES = 20
    MAX_TIMELINE_ITEMS = 100

# ============================================================================
# КОНСТАНТЫ ДЛЯ БЕЗОПАСНОСТИ
# ============================================================================

class SecurityConstants:
    """Константы для безопасности"""
    
    # Пароли
    MIN_PASSWORD_LENGTH = 8
    MAX_PASSWORD_LENGTH = 128
    
    # Сессии
    SESSION_TIMEOUT = 24 * 60 * 60  # 24 часа
    REMEMBER_ME_TIMEOUT = 30 * 24 * 60 * 60  # 30 дней
    
    # Rate limiting
    MAX_REQUESTS_PER_MINUTE = 60
    MAX_REQUESTS_PER_HOUR = 1000
    
    # CSRF
    CSRF_TOKEN_LENGTH = 32

# ============================================================================
# КОНСТАНТЫ ДЛЯ CELERY
# ============================================================================

class CeleryConstants:
    """Константы для Celery задач"""
    
    # Retry настройки
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 60  # секунды
    MAX_RETRY_DELAY = 300  # 5 минут
    
    # Timeout настройки
    TASK_TIMEOUT = 300  # 5 минут
    EMAIL_TASK_TIMEOUT = 60  # 1 минута
    
    # Очереди
    DEFAULT_QUEUE = 'default'
    EMAIL_QUEUE = 'email'
    ANALYTICS_QUEUE = 'analytics'

# ============================================================================
# КОНСТАНТЫ ДЛЯ ВАЛИДАЦИИ
# ============================================================================

class ValidationConstants:
    """Константы для валидации"""
    
    # Регулярные выражения
    PHONE_REGEX = r'^\+?[1-9]\d{1,14}$'
    EMAIL_REGEX = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    FILENAME_REGEX = r'^[a-zA-Z0-9._-]+$'
    
    # Ограничения
    MAX_UPLOAD_FILES_PER_REQUEST = 5
    MAX_CONCURRENT_UPLOADS = 3

# ============================================================================
# КОНСТАНТЫ ДЛЯ ЛОГИРОВАНИЯ
# ============================================================================

class LoggingConstants:
    """Константы для логирования"""
    
    # Уровни логирования
    LOG_LEVEL_DEBUG = 'DEBUG'
    LOG_LEVEL_INFO = 'INFO'
    LOG_LEVEL_WARNING = 'WARNING'
    LOG_LEVEL_ERROR = 'ERROR'
    LOG_LEVEL_CRITICAL = 'CRITICAL'
    
    # Размеры логов
    MAX_LOG_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    MAX_LOG_FILES = 5
    
    # Форматы логов
    LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# ============================================================================
# КОНСТАНТЫ ДЛЯ КЭШИРОВАНИЯ
# ============================================================================

class CacheConstants:
    """Константы для кэширования"""
    
    # Время жизни кэша (в секундах)
    DEFAULT_CACHE_TIMEOUT = 300  # 5 минут
    USER_CACHE_TIMEOUT = 600    # 10 минут
    STATS_CACHE_TIMEOUT = 900   # 15 минут
    
    # Ключи кэша
    USER_PROFILE_CACHE_KEY = 'user_profile_{user_id}'
    ORDER_STATS_CACHE_KEY = 'order_stats_{user_id}'
    FACTORY_LIST_CACHE_KEY = 'factory_list'
    COUNTRY_LIST_CACHE_KEY = 'country_list'

# ============================================================================
# КОНСТАНТЫ ДЛЯ ТЕСТИРОВАНИЯ
# ============================================================================

class TestConstants:
    """Константы для тестирования"""
    
    # Тестовые данные
    TEST_USERNAME = 'testuser'
    TEST_EMAIL = 'test@example.com'
    TEST_PASSWORD = 'testpass123'
    TEST_FACTORY_NAME = 'Test Factory'
    TEST_COUNTRY_NAME = 'Test Country'
    TEST_ORDER_TITLE = 'Test Order'
    
    # Timeout для тестов
    TEST_TIMEOUT = 30  # секунды
    
    # Количество тестовых объектов
    TEST_ORDERS_COUNT = 10
    TEST_FACTORIES_COUNT = 5
    TEST_COUNTRIES_COUNT = 3

# ============================================================================
# КОНСТАНТЫ ДЛЯ МЕЖДУНАРОДИЗАЦИИ
# ============================================================================

class I18nConstants:
    """Константы для интернационализации"""
    
    # Поддерживаемые языки
    SUPPORTED_LANGUAGES = [
        ('ru', 'Русский'),
        ('en', 'English'),
        ('de', 'Deutsch'),
        ('it', 'Italiano'),
        ('zh', '中文'),
        ('tr', 'Türkçe'),
        ('cs', 'Čeština'),
        ('pl', 'Polski'),
        ('lt', 'Lietuvių'),
    ]
    
    # Язык по умолчанию
    DEFAULT_LANGUAGE = 'ru'
    
    # Часовые пояса
    DEFAULT_TIMEZONE = 'Europe/Berlin'
    SUPPORTED_TIMEZONES = [
        'Europe/Berlin',
        'Europe/Moscow',
        'Europe/London',
        'America/New_York',
        'Asia/Shanghai',
    ]

# ============================================================================
# КОНСТАНТЫ ДЛЯ API
# ============================================================================

class ApiConstants:
    """Константы для API"""
    
    # Версии API
    API_VERSION = 'v1'
    API_PREFIX = 'api'
    
    # Лимиты API
    API_RATE_LIMIT = 100  # запросов в час
    API_MAX_PAGE_SIZE = 100
    API_DEFAULT_PAGE_SIZE = 20
    
    # Форматы ответов
    SUPPORTED_FORMATS = ['json', 'xml', 'csv']
    DEFAULT_FORMAT = 'json'
    
    # Коды ошибок
    ERROR_CODE_VALIDATION = 400
    ERROR_CODE_UNAUTHORIZED = 401
    ERROR_CODE_FORBIDDEN = 403
    ERROR_CODE_NOT_FOUND = 404
    ERROR_CODE_SERVER_ERROR = 500

# ============================================================================
# КОНСТАНТЫ ДЛЯ ПРОИЗВОДИТЕЛЬНОСТИ
# ============================================================================

class PerformanceConstants:
    """Константы для производительности"""
    
    # Оптимизация запросов
    MAX_QUERYSET_SIZE = 1000
    DEFAULT_SELECT_RELATED = ['factory', 'factory__country']
    DEFAULT_PREFETCH_RELATED = ['notifications']
    
    # Кэширование запросов
    QUERY_CACHE_TIMEOUT = 60  # секунды
    
    # Пагинация
    OPTIMAL_PAGE_SIZE = 20
    MAX_PAGE_SIZE_FOR_EXPORT = 1000
    
    # Таймауты
    DATABASE_TIMEOUT = 30  # секунды
    REDIS_TIMEOUT = 5     # секунды
    EMAIL_TIMEOUT = 10     # секунды

# ============================================================================
# КОНСТАНТЫ ДЛЯ МОНИТОРИНГА
# ============================================================================

class MonitoringConstants:
    """Константы для мониторинга"""
    
    # Метрики
    METRICS_COLLECTION_INTERVAL = 60  # секунды
    
    # Алерты
    HIGH_CPU_THRESHOLD = 80  # процентов
    HIGH_MEMORY_THRESHOLD = 85  # процентов
    HIGH_DISK_THRESHOLD = 90  # процентов
    
    # Логи
    LOG_ROTATION_SIZE = 10 * 1024 * 1024  # 10MB

# ============================================================================
# КОНСТАНТЫ ДЛЯ РАЗВЕРТЫВАНИЯ
# ============================================================================

class DeploymentConstants:
    """Константы для развертывания"""
    
    # Окружения
    ENVIRONMENT_DEVELOPMENT = 'development'
    ENVIRONMENT_STAGING = 'staging'
    ENVIRONMENT_PRODUCTION = 'production'
    
    # Настройки Docker
    DOCKER_IMAGE_TAG = 'latest'
    DOCKER_REGISTRY = 'registry.example.com'
    
    # Настройки Nginx
    NGINX_MAX_BODY_SIZE = '10m'
    NGINX_TIMEOUT = '30s'
    
    # Настройки базы данных
    DB_CONNECTION_POOL_SIZE = 10
    DB_CONNECTION_TIMEOUT = 30
