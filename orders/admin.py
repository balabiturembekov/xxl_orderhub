from django.contrib import admin
from django.utils.html import format_html
from .models import Country, Factory, Order, NotificationSettings, Notification, NotificationTemplate, UserProfile, Shipment


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'full_name', 'phone', 'department', 'position', 'created_at']
    list_filter = ['department', 'created_at']
    search_fields = ['user__username', 'user__email', 'first_name', 'last_name', 'phone']
    ordering = ['user__username']
    
    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Личная информация', {
            'fields': ('first_name', 'last_name', 'phone')
        }),
        ('Рабочая информация', {
            'fields': ('department', 'position')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'created_at']
    list_filter = ['created_at']
    search_fields = ['name', 'code']
    ordering = ['name']


@admin.register(Factory)
class FactoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'country', 'email', 'contact_person', 'is_active', 'created_at']
    list_filter = ['country', 'is_active', 'created_at']
    search_fields = ['name', 'email', 'contact_person']
    list_editable = ['is_active']
    ordering = ['country', 'name']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'country', 'email', 'is_active')
        }),
        ('Контактная информация', {
            'fields': ('contact_person', 'phone', 'address'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'factory', 'employee', 'status', 'status_badge', 
        'uploaded_at', 'sent_at', 'days_info'
    ]
    list_filter = [
        'status', 'factory__country', 'factory', 'employee', 
        'uploaded_at', 'sent_at'
    ]
    search_fields = ['title', 'description', 'factory__name', 'employee__username']
    readonly_fields = ['uploaded_at', 'sent_at', 'invoice_received_at', 'completed_at']
    list_editable = ['status']
    ordering = ['-uploaded_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('title', 'description', 'factory', 'employee', 'status')
        }),
        ('Файлы', {
            'fields': ('excel_file', 'invoice_file'),
        }),
        ('Даты', {
            'fields': ('uploaded_at', 'sent_at', 'invoice_received_at', 'completed_at'),
            'classes': ('collapse',)
        }),
        ('Комментарии', {
            'fields': ('comments', 'factory_comments'),
            'classes': ('collapse',)
        }),
        ('Уведомления', {
            'fields': ('last_reminder_sent', 'reminder_count'),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'uploaded': 'orange',
            'sent': 'blue',
            'invoice_received': 'green',
            'completed': 'darkgreen',
            'cancelled': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Статус'
    
    def days_info(self, obj):
        if obj.status == 'uploaded':
            days = obj.days_since_upload
            if days >= 7:
                return format_html('<span style="color: red;">{} дней</span>', days)
            return f"{days} дней"
        elif obj.status == 'sent' and obj.days_since_sent:
            days = obj.days_since_sent
            if days >= 7:
                return format_html('<span style="color: red;">{} дней</span>', days)
            return f"{days} дней"
        return '-'
    days_info.short_description = 'Дней с последнего действия'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('factory', 'employee', 'factory__country')


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = ['user', 'email_notifications', 'reminder_frequency', 'notify_uploaded_reminder', 'notify_sent_reminder', 'notify_invoice_received']
    list_filter = ['email_notifications', 'notify_uploaded_reminder', 'notify_sent_reminder', 'notify_invoice_received']
    search_fields = ['user__username', 'user__email']
    ordering = ['user__username']
    
    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Общие настройки', {
            'fields': ('email_notifications', 'reminder_frequency')
        }),
        ('Типы уведомлений', {
            'fields': ('notify_uploaded_reminder', 'notify_sent_reminder', 'notify_invoice_received')
        }),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['title', 'user', 'order', 'notification_type', 'is_read', 'is_sent', 'created_at']
    list_filter = ['notification_type', 'is_read', 'is_sent', 'created_at']
    search_fields = ['title', 'message', 'user__username', 'order__title']
    readonly_fields = ['created_at', 'sent_at', 'read_at']
    ordering = ['-created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'order', 'notification_type', 'title', 'message')
        }),
        ('Статус', {
            'fields': ('is_read', 'is_sent', 'sent_at', 'read_at')
        }),
        ('Метаданные', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'order', 'order__factory')


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ['template_type', 'subject', 'is_active', 'created_at', 'updated_at']
    list_filter = ['template_type', 'is_active', 'created_at']
    search_fields = ['subject', 'template_type']
    ordering = ['template_type']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('template_type', 'subject', 'is_active')
        }),
        ('Шаблоны', {
            'fields': ('html_template', 'text_template')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Shipment)
class ShipmentAdmin(admin.ModelAdmin):
    list_display = ['shipment_number', 'orders_count', 'total_invoice_cbm_display', 'received_cbm_display', 'cbm_difference_display', 'shipment_date', 'created_at']
    list_filter = ['shipment_date', 'received_date', 'created_at']
    search_fields = ['shipment_number', 'notes']
    filter_horizontal = ['orders']
    date_hierarchy = 'shipment_date'
    ordering = ['-shipment_date', '-created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('shipment_number', 'orders')
        }),
        ('Кубы', {
            'fields': ('received_cbm',)
        }),
        ('Даты', {
            'fields': ('shipment_date', 'received_date')
        }),
        ('Дополнительно', {
            'fields': ('notes', 'created_by'),
            'classes': ('collapse',)
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    def orders_count(self, obj):
        """Количество заказов в фуре"""
        return obj.orders_count
    orders_count.short_description = 'Заказов'
    
    def total_invoice_cbm_display(self, obj):
        """Отображение кубов из инвойсов"""
        return f"{obj.total_invoice_cbm:.3f} куб. м"
    total_invoice_cbm_display.short_description = 'Кубы из инвойсов'
    
    def received_cbm_display(self, obj):
        """Отображение фактических кубов"""
        if obj.received_cbm:
            return f"{obj.received_cbm:.3f} куб. м"
        return "-"
    received_cbm_display.short_description = 'Фактические кубы'
    
    def cbm_difference_display(self, obj):
        """Отображение разницы кубов"""
        if obj.cbm_difference is not None:
            diff = obj.cbm_difference
            if diff > 0:
                return format_html('<span style="color: red;">-{:.3f} куб. м</span>', diff)
            elif diff < 0:
                return format_html('<span style="color: green;">+{:.3f} куб. м</span>', abs(diff))
            else:
                return format_html('<span style="color: green;">✓ Совпадает</span>')
        return "-"
    cbm_difference_display.short_description = 'Разница'
