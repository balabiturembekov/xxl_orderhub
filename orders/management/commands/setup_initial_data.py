from django.core.management.base import BaseCommand
from django.db import transaction
from orders.models import Country, Factory


class Command(BaseCommand):
    help = 'Настройка начальных данных: очистка и загрузка производителей'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед загрузкой'
        )

    def handle(self, *args, **options):
        clear_existing = options['clear']
        
        if clear_existing:
            self.stdout.write('Очистка существующих данных...')
            Factory.objects.all().delete()
            Country.objects.all().delete()
            self.stdout.write(
                self.style.SUCCESS('✅ Данные очищены')
            )
        
        # Проверяем, есть ли уже данные
        if Country.objects.count() > 0 or Factory.objects.count() > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f'✅ Данные уже существуют! Найдено {Country.objects.count()} стран и {Factory.objects.count()} фабрик.'
                )
            )
            if not clear_existing:
                self.stdout.write(
                    self.style.WARNING(
                        '💡 Используйте --clear для принудительной перезагрузки данных.'
                    )
                )
                return
        
        # Загружаем данные из JSON файла
        import json
        import os
        
        json_file = 'manufacturer_fixture.json'
        if not os.path.exists(json_file):
            self.stdout.write(
                self.style.ERROR(f'Файл {json_file} не найден!')
            )
            return
        
        with open(json_file, 'r', encoding='utf-8') as f:
            manufacturers_data = json.load(f)
        
        self.stdout.write(f'Найдено {len(manufacturers_data)} производителей')
        
        # Создаем страны и фабрики
        countries_created = set()
        factories_created = 0
        
        with transaction.atomic():
            for i, manufacturer_data in enumerate(manufacturers_data):
                try:
                    fields = manufacturer_data['fields']
                    name = fields['name']
                    email = fields['email_address']
                    phone = fields.get('phone_number', '')
                    
                    # Извлекаем страну из названия
                    country_code = self.extract_country_code(name)
                    country_name = self.get_country_name(country_code)
                    
                    # Создаем или получаем страну
                    country, country_created = Country.objects.get_or_create(
                        code=country_code,
                        defaults={'name': country_name}
                    )
                    
                    if country_created:
                        countries_created.add(country_name)
                    
                    # Создаем фабрику
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
                    
                    # Показываем прогресс
                    if (i + 1) % 50 == 0:
                        self.stdout.write(f'Обработано {i + 1}/{len(manufacturers_data)}...')
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'Ошибка при обработке {name}: {str(e)}')
                    )
                    continue
        
        self.stdout.write(
            self.style.SUCCESS(
                f'✅ Загрузка завершена!\n'
                f'📊 Создано стран: {len(countries_created)}\n'
                f'🏭 Создано фабрик: {factories_created}'
            )
        )
        
        # Выводим список созданных стран
        if countries_created:
            self.stdout.write('\n🌍 Созданные страны:')
            for country in sorted(countries_created):
                self.stdout.write(f'  - {country}')
    
    def extract_country_code(self, name):
        """Извлекает код страны из названия фабрики"""
        if '(' in name and ')' in name:
            parts = name.split('(')
            if len(parts) > 1:
                country_part = parts[-1].rstrip(')')
                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Безопасный доступ к split()[0]
                country_parts = country_part.split()
                if country_parts:
                    country_code = country_parts[0]
                    country_code = country_code.strip(')').strip()
                    
                    # Проверяем, что код не слишком длинный
                    if len(country_code) <= 3:
                        return country_code
        
        return "UNKNOWN"
    
    def get_country_name(self, country_code):
        """Получает полное название страны по коду"""
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
        
        return country_names.get(country_code, f'Страна {country_code}')
