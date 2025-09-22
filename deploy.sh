#!/bin/bash

# Скрипт для развертывания XXL OrderHub на сервере
# Использование: ./deploy.sh

set -e  # Остановить при ошибке

echo "🚀 Начинаем развертывание XXL OrderHub..."

# Проверяем, что docker-compose установлен
if ! command -v docker-compose &> /dev/null; then
    echo "❌ docker-compose не найден. Установите Docker Compose."
    exit 1
fi

# Проверяем, что файлы конфигурации существуют
if [ ! -f "docker-compose.yml" ]; then
    echo "❌ Файл docker-compose.yml не найден."
    exit 1
fi

if [ ! -f "docker.env" ]; then
    echo "❌ Файл docker.env не найден."
    exit 1
fi

if [ ! -f "nginx.conf" ]; then
    echo "❌ Файл nginx.conf не найден."
    exit 1
fi

echo "📦 Останавливаем существующие контейнеры..."
docker-compose down

echo "🔨 Собираем и запускаем контейнеры..."
docker-compose up --build -d

echo "⏳ Ждем запуска сервисов..."
sleep 15

echo "🔍 Проверяем статус сервисов..."
docker-compose ps

echo "🌐 Проверяем доступность приложения..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8280/ | grep -q "200"; then
    echo "✅ Основное приложение работает: http://localhost:8280/"
else
    echo "❌ Основное приложение недоступно"
fi

if curl -s -o /dev/null -w "%{http_code}" --user admin:admin123 http://localhost:8280/flower/ | grep -q "200"; then
    echo "✅ Flower мониторинг работает: http://localhost:8280/flower/ (логин: admin, пароль: admin123)"
else
    echo "❌ Flower мониторинг недоступен"
fi

if curl -s -o /dev/null -w "%{http_code}" http://localhost:8280/static/admin/css/base.css | grep -q "200"; then
    echo "✅ Статические файлы работают"
else
    echo "❌ Статические файлы недоступны"
fi

echo ""
echo "🎉 Развертывание завершено!"
echo ""
echo "📋 Доступные сервисы:"
echo "   • Основное приложение: http://localhost:8280/"
echo "   • Flower мониторинг:   http://localhost:8280/flower/ (логин: admin, пароль: admin123)"
echo "   • Статические файлы:  http://localhost:8280/static/"
echo "   • Медиа файлы:        http://localhost:8280/media/"
echo ""
echo "🔧 Управление:"
echo "   • Остановить:         docker-compose down"
echo "   • Перезапустить:      docker-compose restart"
echo "   • Логи:               docker-compose logs"
echo "   • Статус:             docker-compose ps"
echo ""
echo "⚠️  Важно:"
echo "   • Только порт 8280 доступен снаружи"
echo "   • Все остальные сервисы скрыты внутри Docker сети"
echo "   • Статические файлы собираются автоматически"
