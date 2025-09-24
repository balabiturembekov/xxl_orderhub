from django.core.management.base import BaseCommand
from django.conf import settings
import os
import subprocess


class Command(BaseCommand):
    """
    Команда для проверки статуса переводов.
    
    Проверяет:
    - Наличие файлов переводов
    - Статус компиляции
    - Количество переведенных строк
    - Проблемы с переводами
    """
    
    help = 'Проверяет статус переводов и их компиляцию'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--compile',
            action='store_true',
            help='Принудительно скомпилировать переводы',
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Обновить файлы переводов',
        )
        parser.add_argument(
            '--locale',
            type=str,
            help='Проверить конкретный язык (ru, de)',
        )
    
    def handle(self, *args, **options):
        if options['update']:
            self.update_translations()
        elif options['compile']:
            self.compile_translations()
        else:
            self.check_translations(options.get('locale'))
    
    def check_translations(self, locale=None):
        """Проверить статус переводов."""
        self.stdout.write(
            self.style.SUCCESS('🌍 Проверка статуса переводов...')
        )
        
        # Проверяем настройки
        self.stdout.write(f"  📋 Язык по умолчанию: {settings.LANGUAGE_CODE}")
        self.stdout.write(f"  🌐 Поддержка i18n: {settings.USE_I18N}")
        self.stdout.write(f"  📁 Путь к переводам: {settings.LOCALE_PATHS}")
        
        # Проверяем доступные языки
        if hasattr(settings, 'LANGUAGES'):
            self.stdout.write(f"  🗣️ Доступные языки: {[lang[0] for lang in settings.LANGUAGES]}")
        
        # Проверяем файлы переводов
        locale_path = settings.LOCALE_PATHS[0] if settings.LOCALE_PATHS else 'locale'
        
        if not os.path.exists(locale_path):
            self.stdout.write(
                self.style.ERROR(f"❌ Директория переводов не найдена: {locale_path}")
            )
            return
        
        # Проверяем каждый язык
        languages = [locale] if locale else [lang[0] for lang in settings.LANGUAGES]
        
        for lang in languages:
            self.check_language_status(locale_path, lang)
    
    def check_language_status(self, locale_path, lang):
        """Проверить статус конкретного языка."""
        lang_path = os.path.join(locale_path, lang, 'LC_MESSAGES')
        
        if not os.path.exists(lang_path):
            self.stdout.write(
                self.style.WARNING(f"  ⚠️ Язык {lang}: директория не найдена")
            )
            return
        
        po_file = os.path.join(lang_path, 'django.po')
        mo_file = os.path.join(lang_path, 'django.mo')
        
        # Проверяем .po файл
        if os.path.exists(po_file):
            po_size = os.path.getsize(po_file)
            po_count = self.count_translations(po_file)
            self.stdout.write(f"  📝 {lang}: {po_count} строк, {po_size} байт")
        else:
            self.stdout.write(
                self.style.ERROR(f"  ❌ {lang}: файл .po не найден")
            )
            return
        
        # Проверяем .mo файл
        if os.path.exists(mo_file):
            mo_size = os.path.getsize(mo_file)
            mo_mtime = os.path.getmtime(mo_file)
            po_mtime = os.path.getmtime(po_file) if os.path.exists(po_file) else 0
            
            if mo_mtime > po_mtime:
                self.stdout.write(f"  ✅ {lang}: .mo файл актуален ({mo_size} байт)")
            else:
                self.stdout.write(
                    self.style.WARNING(f"  ⚠️ {lang}: .mo файл устарел, нужна компиляция")
                )
        else:
            self.stdout.write(
                self.style.WARNING(f"  ⚠️ {lang}: файл .mo не найден, нужна компиляция")
            )
    
    def count_translations(self, po_file):
        """Подсчитать количество переводов в .po файле."""
        try:
            with open(po_file, 'r', encoding='utf-8') as f:
                content = f.read()
                return content.count('msgid "')
        except Exception as e:
            self.stdout.write(f"    Ошибка чтения файла: {e}")
            return 0
    
    def update_translations(self):
        """Обновить файлы переводов."""
        self.stdout.write(
            self.style.SUCCESS('📝 Обновление файлов переводов...')
        )
        
        try:
            # Обновляем переводы для всех языков
            result = subprocess.run(
                ['python', 'manage.py', 'makemessages', '--all'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.stdout.write(
                    self.style.SUCCESS('✅ Файлы переводов обновлены!')
                )
                self.stdout.write(result.stdout)
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Ошибка обновления переводов:')
                )
                self.stdout.write(result.stderr)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка: {e}')
            )
    
    def compile_translations(self):
        """Скомпилировать переводы."""
        self.stdout.write(
            self.style.SUCCESS('🔧 Компиляция переводов...')
        )
        
        try:
            result = subprocess.run(
                ['python', 'manage.py', 'compilemessages'],
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                self.stdout.write(
                    self.style.SUCCESS('✅ Переводы скомпилированы!')
                )
                self.stdout.write(result.stdout)
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Ошибка компиляции:')
                )
                self.stdout.write(result.stderr)
                
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибка: {e}')
            )
