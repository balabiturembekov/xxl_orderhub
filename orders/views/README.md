# 📁 Views Module Structure

This directory contains all Django views organized by functionality for better maintainability and code organization.

## 🗂 Module Overview

### 1. `order_views.py` - Order Management
**Purpose**: CRUD operations for orders
- `OrderListView` - List orders with filtering and pagination
- `OrderDetailView` - Detailed order information
- `create_order` - Create new orders
- `download_file` - Download order files (Excel/PDF)
- `preview_file` - Generate file previews
- `preview_file_modal` - Display previews in modal

### 2. `confirmation_views.py` - Confirmation System
**Purpose**: Critical operations confirmation workflow
- `ConfirmationListView` - List all confirmations
- `confirmation_detail` - View confirmation details
- `send_order` - Create send order confirmation
- `upload_invoice` - Create invoice upload confirmation
- `upload_invoice_form` - Display invoice upload form
- `upload_invoice_execute` - Execute invoice upload
- `complete_order` - Create order completion confirmation
- `confirmation_approve` - Approve and execute operations
- `confirmation_reject` - Reject operations

### 3. `notification_views.py` - Notification Management
**Purpose**: User notification system
- `NotificationListView` - List user notifications
- `mark_notification_read` - Mark notification as read
- `mark_all_notifications_read` - Mark all notifications as read
- `notification_settings` - Manage notification preferences
- `test_notification` - Send test notifications

### 4. `analytics_views.py` - Analytics & Reporting
**Purpose**: Data analytics and reporting
- `AnalyticsDashboardView` - Main analytics dashboard
- `analytics_export` - Export analytics data to CSV
- `analytics_api` - JSON API for charts and graphs

### 5. `management_views.py` - Reference Data Management
**Purpose**: CRUD operations for reference data
- `CountryListView` - List countries
- `CountryCreateView` - Create countries
- `CountryUpdateView` - Update countries
- `country_delete` - Delete countries
- `FactoryListView` - List factories
- `FactoryCreateView` - Create factories
- `FactoryUpdateView` - Update factories
- `factory_delete` - Delete factories

### 6. `auth_views.py` - Authentication
**Purpose**: User authentication and home page
- `SignUpView` - User registration
- `HomeView` - Home page with user-specific content

### 7. `api_views.py` - AJAX API Endpoints
**Purpose**: AJAX endpoints for dynamic frontend functionality
- `get_factories` - Get factories (with optional country filter)
- `get_countries` - Get all countries
- `create_country_ajax` - Create country via AJAX
- `create_factory_ajax` - Create factory via AJAX
- `get_order_status` - Get order status
- `get_user_statistics` - Get user statistics
- `search_factories` - Search factories
- `get_factory_details` - Get detailed factory information

## 🔧 Usage Examples

### Adding a New View

1. **Determine the appropriate module** based on functionality
2. **Add the view function** with proper documentation
3. **Update `__init__.py`** to export the new view
4. **Add URL pattern** in `urls.py`
5. **Create template** if needed
6. **Add tests** for the new functionality

### Example: Adding a New Order View

```python
# In order_views.py
@login_required
def edit_order(request, pk: int):
    """
    Edit an existing order.
    
    Args:
        pk: Order primary key
    
    Returns:
        Rendered order edit form or redirect to order detail
    """
    order = get_object_or_404(Order, pk=pk, employee=request.user)
    
    if request.method == 'POST':
        form = OrderForm(request.POST, request.FILES, instance=order)
        if form.is_valid():
            form.save()
            messages.success(request, f'Заказ "{order.title}" успешно обновлен!')
            return redirect('order_detail', pk=order.pk)
    else:
        form = OrderForm(instance=order)
    
    return render(request, 'orders/order_edit.html', {
        'form': form,
        'order': order
    })
```

### Example: Adding a New API Endpoint

```python
# In api_views.py
@login_required
@require_http_methods(["GET"])
def get_order_timeline(request, pk: int):
    """
    Get order timeline for visualization.
    
    Args:
        pk: Order primary key
    
    Returns:
        JsonResponse with timeline data
    """
    order = get_object_or_404(Order, pk=pk, employee=request.user)
    
    timeline = [
        {
            'date': order.uploaded_at.isoformat(),
            'event': 'Заказ загружен',
            'status': 'uploaded'
        }
    ]
    
    if order.sent_at:
        timeline.append({
            'date': order.sent_at.isoformat(),
            'event': 'Заказ отправлен',
            'status': 'sent'
        })
    
    return JsonResponse({'timeline': timeline})
```

## 📋 Best Practices

### 1. Documentation
- Always add docstrings to functions and classes
- Include parameter types and return types
- Document any exceptions that might be raised

### 2. Error Handling
- Use `get_object_or_404` for object retrieval
- Handle form validation errors gracefully
- Provide meaningful error messages to users

### 3. Security
- Use `@login_required` decorator for protected views
- Validate user permissions for sensitive operations
- Sanitize user input

### 4. Performance
- Use `select_related` and `prefetch_related` for database optimization
- Implement caching for expensive operations
- Use pagination for large datasets

### 5. Code Organization
- Keep views focused on single responsibilities
- Extract complex logic into separate functions
- Use type hints for better code clarity

## 🧪 Testing Views

### Example Test Structure

```python
from django.test import TestCase, Client
from django.contrib.auth.models import User
from orders.models import Order, Factory

class OrderViewsTest(TestCase):
    """Test cases for order views."""
    
    def setUp(self):
        """Set up test data."""
        self.client = Client()
        self.user = User.objects.create_user('testuser', 'test@example.com', 'password')
        self.factory = Factory.objects.create(name='Test Factory')
    
    def test_order_list_requires_login(self):
        """Test that order list requires authentication."""
        response = self.client.get('/orders/')
        self.assertEqual(response.status_code, 302)  # Redirect to login
    
    def test_order_list_authenticated(self):
        """Test order list for authenticated user."""
        self.client.login(username='testuser', password='password')
        response = self.client.get('/orders/')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'orders')
```

## 🔄 Migration from Old Structure

The views were previously all in a single `views.py` file (1418 lines, 39 functions). The new modular structure provides:

- **Better organization** - Related views grouped together
- **Easier maintenance** - Smaller, focused files
- **Improved readability** - Clear separation of concerns
- **Better testing** - Easier to write focused tests
- **Team collaboration** - Multiple developers can work on different modules

## 📚 Related Documentation

- [Developer Guide](../DEVELOPER_GUIDE.md) - Comprehensive development guide
- [Models Documentation](../models.py) - Data models reference
- [Forms Documentation](../forms.py) - Form definitions
- [URLs Configuration](../urls.py) - URL routing
