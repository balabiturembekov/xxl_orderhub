#!/usr/bin/env python
"""
Скрипт для загрузки производителей из JSON фикстуры
"""
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xxl_orderhub.settings')
django.setup()

import json
from orders.models import Country, Factory


def load_manufacturers():
    """Загружает производителей из JSON файла"""
    
    # Загружаем данные
    with open('manufacturer_fixture.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    print(f'Найдено {len(data)} производителей')
    
    countries_created = set()
    factories_created = 0
    
    for i, item in enumerate(data):
        try:
            fields = item['fields']
            name = fields['name']
            email = fields['email_address']
            phone = fields.get('phone_number', '')
            
            # Извлекаем страну из названия
            if '(' in name and ')' in name:
                country_code = name.split('(')[-1].rstrip(')').split()[0]
            else:
                country_code = 'UNKNOWN'
            
            # Получаем название страны
            country_names = {
                'IT': 'Италия',
                'TR': 'Турция',
                'DE': 'Германия',
                'FR': 'Франция',
                'ES': 'Испания',
                'PL': 'Польша',
                'RO': 'Румыния',
                'BG': 'Болгария',
                'HU': 'Венгрия',
                'CZ': 'Чехия',
                'SK': 'Словакия',
                'HR': 'Хорватия',
                'SI': 'Словения',
                'AT': 'Австрия',
                'CH': 'Швейцария',
                'NL': 'Нидерланды',
                'BE': 'Бельгия',
                'DK': 'Дания',
                'SE': 'Швеция',
                'NO': 'Норвегия',
                'FI': 'Финляндия',
                'PT': 'Португалия',
                'GR': 'Греция',
                'CY': 'Кипр',
                'MT': 'Мальта',
                'IE': 'Ирландия',
                'LU': 'Люксембург',
                'EE': 'Эстония',
                'LV': 'Латвия',
                'LT': 'Литва',
                'UNKNOWN': 'Неизвестная страна'
            }
            
            country_name = country_names.get(country_code, f'Страна {country_code}')
            
            # Создаем или получаем страну
            country, country_created = Country.objects.get_or_create(
                code=country_code,
                defaults={'name': country_name}
            )
            
            if country_created:
                countries_created.add(country_name)
            
            # Создаем или получаем фабрику
            factory, factory_created = Factory.objects.get_or_create(
                name=name,
                defaults={
                    'country': country,
                    'email': email,
                    'phone': phone,
                    'contact_person': '',
                    'address': ''
                }
            )
            
            if factory_created:
                factories_created += 1
            
            # Показываем прогресс каждые 50 записей
            if (i + 1) % 50 == 0:
                print(f'Обработано {i + 1}/{len(data)} производителей...')
                
        except Exception as e:
            print(f'Ошибка при обработке {name}: {str(e)}')
            continue
    
    print(f'\n✅ Загрузка завершена!')
    print(f'📊 Создано стран: {len(countries_created)}')
    print(f'🏭 Создано фабрик: {factories_created}')
    
    # Выводим список созданных стран
    if countries_created:
        print('\n🌍 Созданные страны:')
        for country in sorted(countries_created):
            print(f'  - {country}')


if __name__ == '__main__':
    load_manufacturers()
