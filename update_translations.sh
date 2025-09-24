#!/bin/bash

# Скрипт для обновления переводов
# Используется для обновления переводов на сервере

echo "🌍 Обновление переводов..."

# Проверяем, что мы в правильной директории
if [ ! -f "manage.py" ]; then
    echo "❌ Ошибка: manage.py не найден. Запустите скрипт из корневой директории проекта."
    exit 1
fi

# Проверяем наличие gettext
if ! command -v msgfmt &> /dev/null; then
    echo "❌ Ошибка: gettext не установлен. Установите: apt-get install gettext"
    exit 1
fi

echo "📝 Создание файлов переводов..."
python manage.py makemessages -l ru
python manage.py makemessages -l de

echo "🔧 Компиляция переводов..."
python manage.py compilemessages

echo "✅ Переводы обновлены!"
echo ""
echo "📊 Статистика переводов:"
echo "  🇷🇺 Русский:"
if [ -f "locale/ru/LC_MESSAGES/django.po" ]; then
    RU_COUNT=$(grep -c "^msgid" locale/ru/LC_MESSAGES/django.po)
    echo "    - Всего строк: $RU_COUNT"
else
    echo "    - Файл не найден"
fi

echo "  🇩🇪 Немецкий:"
if [ -f "locale/de/LC_MESSAGES/django.po" ]; then
    DE_COUNT=$(grep -c "^msgid" locale/de/LC_MESSAGES/django.po)
    echo "    - Всего строк: $DE_COUNT"
else
    echo "    - Файл не найден"
fi

echo ""
echo "🚀 Готово! Перезапустите сервер для применения изменений."
