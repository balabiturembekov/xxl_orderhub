from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Аутентификация
    path("accounts/signup/", views.SignUpView.as_view(), name="signup"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page='/'), name="logout"),
    path("accounts/password_reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("accounts/password_reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    
    # Основные страницы
    path("", views.HomeView.as_view(), name="home"),
    
    # Заказы
    path("orders/", views.OrderListView.as_view(), name="order_list"),
    path("orders/create/", views.create_order, name="create_order"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:pk>/send/", views.send_order, name="send_order"),
    path("orders/<int:pk>/upload-invoice/", views.upload_invoice, name="upload_invoice"),
    path("orders/<int:pk>/download/<str:file_type>/", views.download_file, name="download_file"),
    
    # AJAX endpoints
    path("api/factories/", views.get_factories, name="get_factories"),
    
    # Уведомления
    path("notifications/", views.notification_list, name="notification_list"),
    path("notifications/<int:pk>/read/", views.mark_notification_read, name="mark_notification_read"),
    path("notifications/mark-all-read/", views.mark_all_notifications_read, name="mark_all_notifications_read"),
    path("notifications/settings/", views.notification_settings, name="notification_settings"),
    
    # Аналитика
    path("analytics/", views.AnalyticsDashboardView.as_view(), name="analytics_dashboard"),
    path("analytics/export/", views.analytics_export, name="analytics_export"),
    path("api/analytics/", views.analytics_api, name="analytics_api"),
    
    # Утилиты
    path("clear-messages/", views.clear_messages, name="clear_messages"),
    
    # Управление странами
    path("countries/", views.CountryListView.as_view(), name="country_list"),
    path("countries/create/", views.CountryCreateView.as_view(), name="country_create"),
    path("countries/<int:pk>/edit/", views.CountryUpdateView.as_view(), name="country_edit"),
    path("countries/<int:pk>/delete/", views.country_delete, name="country_delete"),
    
    # Управление фабриками
    path("factories/", views.FactoryListView.as_view(), name="factory_list"),
    path("factories/create/", views.FactoryCreateView.as_view(), name="factory_create"),
    path("factories/<int:pk>/edit/", views.FactoryUpdateView.as_view(), name="factory_edit"),
    path("factories/<int:pk>/delete/", views.factory_delete, name="factory_delete"),
    
    # AJAX endpoints для управления
    path("api/countries/", views.get_countries, name="get_countries"),
    path("api/countries/create/", views.create_country_ajax, name="create_country_ajax"),
    path("api/factories/create/", views.create_factory_ajax, name="create_factory_ajax"),
    
    # Предварительный просмотр файлов
    path("orders/<int:pk>/preview/<str:file_type>/", views.preview_file, name="preview_file"),
    path("orders/<int:pk>/preview-modal/<str:file_type>/", views.preview_file_modal, name="preview_file_modal"),
    
    # Тестирование уведомлений
    path("notifications/test/", views.test_notification, name="test_notification"),
    
    # Завершение заказа
    path("orders/<int:pk>/complete/", views.complete_order, name="complete_order"),
]