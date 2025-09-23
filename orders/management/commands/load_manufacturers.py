import json
import os
from django.core.management.base import BaseCommand
from django.db import transaction
from orders.models import Country, Factory


class Command(BaseCommand):
    help = 'Загружает производителей из JSON фикстуры'

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            type=str,
            default='manufacturer_fixture.json',
            help='Путь к JSON файлу с данными производителей'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Очистить существующие данные перед загрузкой'
        )

    def handle(self, *args, **options):
        file_path = options['file']
        clear_existing = options['clear']
        
        if not os.path.exists(file_path):
            self.stdout.write(
                self.style.ERROR(f'Файл {file_path} не найден!')
            )
            return
        
        # Очищаем существующие данные если нужно
        if clear_existing:
            self.stdout.write('Очистка существующих данных...')
            Factory.objects.all().delete()
            Country.objects.all().delete()
        
        # Загружаем данные из JSON
        with open(file_path, 'r', encoding='utf-8') as f:
            manufacturers_data = json.load(f)
        
        self.stdout.write(f'Найдено {len(manufacturers_data)} производителей')
        
        # Создаем страны и фабрики
        countries_created = set()
        factories_created = 0
        
        with transaction.atomic():
            for manufacturer_data in manufacturers_data:
                try:
                    fields = manufacturer_data['fields']
                    name = fields['name']
                    email = fields['email_address']
                    phone = fields.get('phone_number', '')
                    
                    # Извлекаем страну из названия (последние символы в скобках)
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
                            'contact_person': '',  # Можно добавить позже
                            'address': ''  # Можно добавить позже
                        }
                    )
                    
                    if factory_created:
                        factories_created += 1
                    
                except Exception as e:
                    self.stdout.write(
                        self.style.WARNING(f'Ошибка при обработке {name}: {str(e)}')
                    )
                    continue
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Загрузка завершена!\n'
                f'Создано стран: {len(countries_created)}\n'
                f'Создано фабрик: {factories_created}'
            )
        )
        
        # Выводим список созданных стран
        if countries_created:
            self.stdout.write('\nСозданные страны:')
            for country in sorted(countries_created):
                self.stdout.write(f'  - {country}')
    
    def extract_country_code(self, name):
        """Извлекает код страны из названия фабрики"""
        # Ищем код страны в скобках в конце названия
        if '(' in name and ')' in name:
            # Берем последнюю часть в скобках
            parts = name.split('(')
            if len(parts) > 1:
                country_part = parts[-1].rstrip(')')
                # Убираем дату если есть (например "20.12.24")
                country_code = country_part.split()[0]
                
                # Очищаем код от лишних символов
                country_code = country_code.strip(')').strip()
                
                # Проверяем, что код не слишком длинный
                if len(country_code) <= 3:
                    return country_code
        
        # Если код не найден, возвращаем "UNKNOWN"
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
