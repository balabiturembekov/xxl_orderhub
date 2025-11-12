from django.urls import path
from django.contrib.auth import views as auth_views
from .views import (
    # Order views
    OrderListView, OrderDetailView, create_order, download_file, preview_file, preview_file_modal,
    # Confirmation views
    ConfirmationListView, confirmation_detail, send_order, upload_invoice, upload_invoice_form,
    upload_invoice_execute, complete_order, confirmation_approve, confirmation_reject,
    # Notification views
    NotificationListView, mark_notification_read, mark_all_notifications_read,
    notification_settings, test_notification,
    # Analytics views
    AnalyticsDashboardView, analytics_export, analytics_api, CBMAnalyticsView,
    # Management views
    CountryListView, CountryCreateView, CountryUpdateView, country_delete,
    FactoryListView, FactoryCreateView, FactoryUpdateView, factory_delete,
    # Auth views
    SignUpView, HomeView,
    # Profile views
    ProfileView, edit_profile, change_email, profile_settings,
    # Payment views
    InvoiceDetailView, InvoiceListView, PaymentCreateView, PaymentUpdateView,
    upload_invoice_with_payment, delete_payment, payment_analytics,
    CBMCreateView, CBMUpdateView, delete_cbm,
    # Shipment views
    ShipmentListView, ShipmentDetailView, ShipmentCreateView,
    ShipmentUpdateView, ShipmentDeleteView,
)
from .views.email_template_views import (
    EmailTemplateListView, EmailTemplateDetailView, EmailTemplateCreateView,
    EmailTemplateUpdateView, EmailTemplateDeleteView, email_template_preview,
    email_template_duplicate, email_template_activate, email_template_set_default,
    email_template_export, email_template_import, email_template_variables_help,
    email_template_preview_ajax
)
from .views.api_views import (
    get_factories, get_countries, create_country_ajax, create_factory_ajax
)

urlpatterns = [
    # Аутентификация
    path("accounts/signup/", SignUpView.as_view(), name="signup"),
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page='/'), name="logout"),
    path("accounts/password_reset/", auth_views.PasswordResetView.as_view(), name="password_reset"),
    path("accounts/password_reset/done/", auth_views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("accounts/reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("accounts/reset/done/", auth_views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
    
    # Основные страницы
    path("", HomeView.as_view(), name="home"),
    
    # Профиль пользователя
    path("profile/", ProfileView.as_view(), name="profile"),
    path("profile/edit/", edit_profile, name="edit_profile"),
    path("profile/change-email/", change_email, name="change_email"),
    path("profile/settings/", profile_settings, name="profile_settings"),
    
    # Заказы
    path("orders/", OrderListView.as_view(), name="order_list"),
    path("orders/create/", create_order, name="create_order"),
    path("orders/<int:pk>/", OrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:pk>/send/", send_order, name="send_order"),
    path("orders/<int:pk>/upload-invoice/", upload_invoice, name="upload_invoice"),
    path("orders/<int:pk>/upload-invoice-form/", upload_invoice_form, name="upload_invoice_form"),
    path("orders/<int:pk>/upload-invoice-execute/", upload_invoice_execute, name="upload_invoice_execute"),
    path("orders/<int:pk>/complete/", complete_order, name="complete_order"),
    path("orders/<int:pk>/download/<str:file_type>/", download_file, name="download_file"),
    
    # AJAX endpoints
    path("api/factories/", get_factories, name="get_factories"),
    
    # Уведомления
    path("notifications/", NotificationListView.as_view(), name="notification_list"),
    path("notifications/<int:pk>/read/", mark_notification_read, name="mark_notification_read"),
    path("notifications/mark-all-read/", mark_all_notifications_read, name="mark_all_notifications_read"),
    path("notifications/settings/", notification_settings, name="notification_settings"),
    path("notifications/test/", test_notification, name="test_notification"),
    
    # Аналитика
    path("analytics/", AnalyticsDashboardView.as_view(), name="analytics_dashboard"),
    path("analytics/export/", analytics_export, name="analytics_export"),
    path("api/analytics/", analytics_api, name="analytics_api"),
    path("analytics/cbm/", CBMAnalyticsView.as_view(), name="cbm_analytics"),
    
    # Подтверждения
    path("confirmations/", ConfirmationListView.as_view(), name="confirmation_list"),
    path("confirmations/<int:pk>/", confirmation_detail, name="confirmation_detail"),
    path("confirmations/<int:pk>/approve/", confirmation_approve, name="confirmation_approve"),
    path("confirmations/<int:pk>/reject/", confirmation_reject, name="confirmation_reject"),
    
    # Управление странами
    path("countries/", CountryListView.as_view(), name="country_list"),
    path("countries/create/", CountryCreateView.as_view(), name="country_create"),
    path("countries/<int:pk>/edit/", CountryUpdateView.as_view(), name="country_edit"),
    path("countries/<int:pk>/delete/", country_delete, name="country_delete"),
    
    # Управление фабриками
    path("factories/", FactoryListView.as_view(), name="factory_list"),
    path("factories/create/", FactoryCreateView.as_view(), name="factory_create"),
    path("factories/<int:pk>/edit/", FactoryUpdateView.as_view(), name="factory_edit"),
    path("factories/<int:pk>/delete/", factory_delete, name="factory_delete"),
    
    # AJAX endpoints для управления
    path("api/countries/", get_countries, name="get_countries"),
    path("api/countries/create/", create_country_ajax, name="create_country_ajax"),
    path("api/factories/create/", create_factory_ajax, name="create_factory_ajax"),
    
    # Предварительный просмотр файлов
    path("orders/<int:pk>/preview/<str:file_type>/", preview_file, name="preview_file"),
    path("orders/<int:pk>/preview-modal/<str:file_type>/", preview_file_modal, name="preview_file_modal"),
    
    # Управление инвойсами и платежами
    path("invoices/", InvoiceListView.as_view(), name="invoice_list"),
    path("invoices/<int:pk>/", InvoiceDetailView.as_view(), name="invoice_detail"),
    path("invoices/<int:invoice_id>/payments/create/", PaymentCreateView.as_view(), name="payment_create"),
    path("payments/<int:pk>/edit/", PaymentUpdateView.as_view(), name="payment_update"),
    path("payments/<int:payment_id>/delete/", delete_payment, name="payment_delete"),
    path("orders/<int:order_id>/upload-invoice-with-payment/", upload_invoice_with_payment, name="upload_invoice_with_payment"),
    path("payment-analytics/", payment_analytics, name="payment_analytics"),
    
    # Управление CBM
    path("orders/<int:order_id>/cbm/create/", CBMCreateView.as_view(), name="cbm_create"),
    path("cbm/<int:pk>/edit/", CBMUpdateView.as_view(), name="cbm_update"),
    path("cbm/<int:cbm_id>/delete/", delete_cbm, name="cbm_delete"),
    
    # Управление фурами
    path("shipments/", ShipmentListView.as_view(), name="shipment_list"),
    path("shipments/create/", ShipmentCreateView.as_view(), name="shipment_create"),
    path("shipments/<int:pk>/", ShipmentDetailView.as_view(), name="shipment_detail"),
    path("shipments/<int:pk>/edit/", ShipmentUpdateView.as_view(), name="shipment_update"),
    path("shipments/<int:pk>/delete/", ShipmentDeleteView.as_view(), name="shipment_delete"),
    
    # Управление email шаблонами
    path("email-templates/", EmailTemplateListView.as_view(), name="email_template_list"),
    path("email-templates/create/", EmailTemplateCreateView.as_view(), name="email_template_create"),
    path("email-templates/<int:pk>/", EmailTemplateDetailView.as_view(), name="email_template_detail"),
    path("email-templates/<int:pk>/edit/", EmailTemplateUpdateView.as_view(), name="email_template_update"),
    path("email-templates/<int:pk>/delete/", EmailTemplateDeleteView.as_view(), name="email_template_delete"),
    path("email-templates/<int:pk>/preview/", email_template_preview, name="email_template_preview"),
    path("email-templates/<int:pk>/duplicate/", email_template_duplicate, name="email_template_duplicate"),
    path("email-templates/<int:pk>/activate/", email_template_activate, name="email_template_activate"),
    path("email-templates/<int:pk>/set-default/", email_template_set_default, name="email_template_set_default"),
    path("email-templates/<int:pk>/export/", email_template_export, name="email_template_export"),
    path("email-templates/import/", email_template_import, name="email_template_import"),
    path("email-templates/variables-help/", email_template_variables_help, name="email_template_variables_help"),
    path("email-templates/preview-ajax/", email_template_preview_ajax, name="email_template_preview_ajax"),
]