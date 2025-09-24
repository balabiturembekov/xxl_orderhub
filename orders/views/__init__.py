"""
Views package for XXL OrderHub application.

This package contains all view modules organized by functionality:
- order_views: Order CRUD operations
- confirmation_views: Order confirmation system
- notification_views: Notification management
- analytics_views: Analytics and reporting
- management_views: Country and factory management
- auth_views: Authentication views
- profile_views: User profile management
- payment_views: Invoice and payment management
- api_views: AJAX API endpoints
"""

from .order_views import *
from .confirmation_views import *
from .notification_views import *
from .analytics_views import *
from .management_views import *
from .auth_views import *
from .profile_views import *
from .payment_views import *
from .api_views import *
