#!/usr/bin/env python3
"""
Тест для проверки работы переводов
"""
import os
import sys
import django
from django.conf import settings

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xxl_orderhub.settings')
django.setup()

from django.utils import translation
from django.template.loader import render_to_string
from django.template import Context, Template

def test_translations():
    print("🔍 Тестирование переводов...")
    
    # Проверяем доступные языки
    print(f"📋 Доступные языки: {settings.LANGUAGES}")
    print(f"🌍 Текущий язык по умолчанию: {settings.LANGUAGE_CODE}")
    print(f"📁 Пути к переводам: {settings.LOCALE_PATHS}")
    
    # Проверяем файлы переводов
    for lang_code, lang_name in settings.LANGUAGES:
        locale_path = os.path.join(settings.BASE_DIR, 'locale', lang_code, 'LC_MESSAGES')
        po_file = os.path.join(locale_path, 'django.po')
        mo_file = os.path.join(locale_path, 'django.mo')
        
        print(f"\n🌐 Язык: {lang_name} ({lang_code})")
        print(f"   📄 PO файл: {'✅' if os.path.exists(po_file) else '❌'} {po_file}")
        print(f"   📦 MO файл: {'✅' if os.path.exists(mo_file) else '❌'} {mo_file}")
        
        if os.path.exists(mo_file):
            size = os.path.getsize(mo_file)
            print(f"   📊 Размер MO файла: {size} байт")
    
    # Тестируем переводы
    print(f"\n🧪 Тестирование переводов:")
    
    test_strings = [
        "Создать заказ",
        "Настройки уведомлений", 
        "Подтверждения",
        "Аналитика"
    ]
    
    for lang_code, lang_name in settings.LANGUAGES:
        print(f"\n🌐 Тест для языка: {lang_name}")
        translation.activate(lang_code)
        
        for test_string in test_strings:
            try:
                translated = translation.gettext(test_string)
                status = "✅" if translated != test_string else "⚠️"
                print(f"   {status} '{test_string}' → '{translated}'")
            except Exception as e:
                print(f"   ❌ Ошибка перевода '{test_string}': {e}")
        
        translation.deactivate()
    
    print(f"\n✅ Тест завершен!")

if __name__ == "__main__":
    test_translations()
