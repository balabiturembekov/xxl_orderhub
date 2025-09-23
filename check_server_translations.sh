#!/bin/bash

echo "🔍 Проверка переводов на сервере..."

echo "📋 Проверяем файлы переводов в контейнере:"
sudo docker-compose exec web ls -la /app/locale/

echo ""
echo "🌐 Проверяем немецкие переводы:"
sudo docker-compose exec web ls -la /app/locale/de/LC_MESSAGES/

echo ""
echo "🌐 Проверяем русские переводы:"
sudo docker-compose exec web ls -la /app/locale/ru/LC_MESSAGES/

echo ""
echo "🧪 Тестируем переводы в контейнере:"
sudo docker-compose exec web python manage.py shell -c "
from django.utils import translation
from django.conf import settings

print('Доступные языки:', settings.LANGUAGES)
print('Текущий язык:', settings.LANGUAGE_CODE)

# Тестируем переводы
test_strings = ['Создать заказ', 'Настройки уведомлений', 'Подтверждения']

for lang_code, lang_name in settings.LANGUAGES:
    print(f'\\nЯзык: {lang_name}')
    translation.activate(lang_code)
    for test_string in test_strings:
        translated = translation.gettext(test_string)
        status = '✅' if translated != test_string else '⚠️'
        print(f'  {status} {test_string} → {translated}')
    translation.deactivate()
"

echo ""
echo "🔄 Перекомпилируем переводы:"
sudo docker-compose exec web python manage.py compilemessages

echo ""
echo "✅ Проверка завершена!"
