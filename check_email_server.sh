#!/bin/bash

# Скрипт для проверки настроек email на сервере
# Использование: ./check_email_server.sh [email@example.com]

echo "🔍 ДИАГНОСТИКА EMAIL НА СЕРВЕРЕ"
echo "================================="

# Проверяем, что docker-compose.prod.yml существует
if [ ! -f "docker-compose.prod.yml" ]; then
    echo "❌ Файл docker-compose.prod.yml не найден."
    exit 1
fi

# Проверяем, что контейнеры запущены
echo "📦 Проверка статуса контейнеров..."
docker-compose -f docker-compose.prod.yml ps

echo ""
echo "🔧 Проверка переменных окружения в контейнере web..."
docker-compose -f docker-compose.prod.yml exec web printenv | grep -E "EMAIL|DEFAULT_FROM" | sort

echo ""
echo "📧 Проверка настроек Django email..."
docker-compose -f docker-compose.prod.yml exec web python manage.py check_email_settings

# Если передан email адрес, отправляем тестовое письмо
if [ ! -z "$1" ]; then
    echo ""
    echo "📤 Отправка тестового письма на $1..."
    docker-compose -f docker-compose.prod.yml exec web python manage.py check_email_settings --send-test --test-email "$1"
else
    echo ""
    echo "💡 Для отправки тестового письма запустите:"
    echo "   ./check_email_server.sh your@email.com"
fi

echo ""
echo "📋 Логи последних email операций..."
echo "--- Worker logs (последние 20 строк) ---"
docker-compose -f docker-compose.prod.yml logs worker --tail=20 | grep -i email || echo "Email логи не найдены в worker"

echo ""
echo "--- Web logs (последние 20 строк) ---"  
docker-compose -f docker-compose.prod.yml logs web --tail=20 | grep -i email || echo "Email логи не найдены в web"

echo ""
echo "🔍 Проверка файла docker.env..."
if [ -f "docker.env" ]; then
    echo "✅ Файл docker.env найден"
    echo "📧 Email настройки в docker.env:"
    grep -E "EMAIL|DEFAULT_FROM" docker.env | sed 's/EMAIL_HOST_PASSWORD=.*/EMAIL_HOST_PASSWORD=***СКРЫТ***/'
else
    echo "❌ Файл docker.env не найден!"
fi

echo ""
echo "🎯 РЕКОМЕНДАЦИИ:"
echo "1. Убедитесь, что используется docker-compose.prod.yml (не docker-compose.yml)"
echo "2. Проверьте, что docker.env содержит правильные настройки SMTP"
echo "3. Убедитесь, что контейнеры перезапущены после изменения docker.env"
echo "4. Проверьте логи worker для ошибок отправки email"
echo ""
echo "🔄 Для перезапуска с новыми настройками:"
echo "   docker-compose -f docker-compose.prod.yml down"
echo "   docker-compose -f docker-compose.prod.yml up -d"
