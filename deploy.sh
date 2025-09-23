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
docker-compose down --remove-orphans

echo "🧹 Удаляем конфликтующие контейнеры..."
# Удаляем старый nginx контейнер если он существует
docker rm -f xxl_orderhub_nginx 2>/dev/null || true

echo "🔨 Собираем и запускаем контейнеры..."
docker-compose up --build -d

echo "⏳ Ждем запуска сервисов..."
sleep 15

echo "🔍 Проверяем статус сервисов..."
docker-compose ps

echo "📊 Настройка начальных данных..."
# Проверяем, есть ли JSON файл с данными производителей
if [ -f "manufacturer_fixture.json" ]; then
    echo "📁 Копируем JSON файл в контейнер..."
    docker cp manufacturer_fixture.json xxl_orderhub-web-1:/app/
    
    # Копируем команды управления если их нет
    if ! docker-compose exec web test -f orders/management/commands/setup_initial_data.py; then
        echo "📁 Копируем команды управления..."
        docker cp orders/management/commands/setup_initial_data.py xxl_orderhub-web-1:/app/orders/management/commands/
    fi
    
    echo "🏭 Загружаем данные производителей..."
    # Проверяем, что команда существует
    if docker-compose exec web python manage.py help setup_initial_data >/dev/null 2>&1; then
        docker-compose exec --user root web python manage.py setup_initial_data
    else
        echo "⚠️ Команда setup_initial_data не найдена. Пропускаем загрузку данных."
    fi
    
    echo "✅ Данные производителей загружены!"
    
    echo "🔍 Проверяем целостность данных..."
    if docker-compose exec web python manage.py help check_data_integrity >/dev/null 2>&1; then
        docker-compose exec web python manage.py check_data_integrity
    fi
else
    echo "⚠️ Файл manufacturer_fixture.json не найден. Пропускаем загрузку данных."
fi

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
echo "   • Проверить данные:   docker-compose exec web python manage.py check_data_integrity"
echo "   • Перезагрузить данные: docker-compose exec --user root web python manage.py setup_initial_data --clear"
echo "   • Очистить справочники: docker-compose exec web python manage.py clear_reference_data --force"
echo ""
echo "⚠️  Важно:"
echo "   • Только порт 8280 доступен снаружи"
echo "   • Все остальные сервисы скрыты внутри Docker сети"
echo "   • Статические файлы собираются автоматически"
