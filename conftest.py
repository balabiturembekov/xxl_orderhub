import os
import django
from django.conf import settings

# Настройка Django для pytest
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xxl_orderhub.settings')
django.setup()
