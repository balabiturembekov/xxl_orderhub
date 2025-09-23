#!/bin/bash

# Скрипт для настройки начальных данных
# Загружает производителей из JSON фикстуры

echo "🚀 Настройка начальных данных..."

# Проверяем, что контейнер запущен
if ! docker-compose ps | grep -q "web.*Up"; then
    echo "❌ Контейнер web не запущен. Запускаем..."
    docker-compose up -d web
    sleep 10
fi

# Копируем JSON файл в контейнер если его нет
if ! docker-compose exec web test -f manufacturer_fixture.json; then
    echo "📁 Копируем JSON файл в контейнер..."
    docker cp manufacturer_fixture.json xxl_orderhub-web-1:/app/
fi

# Копируем команды управления если их нет
if ! docker-compose exec web test -f orders/management/commands/setup_initial_data.py; then
    echo "📁 Копируем команды управления..."
    docker cp orders/management/commands/setup_initial_data.py xxl_orderhub-web-1:/app/orders/management/commands/
fi

# Запускаем команду настройки данных
echo "📊 Загружаем данные производителей..."
docker-compose exec --user root web python manage.py setup_initial_data --clear

echo "✅ Настройка данных завершена!"
echo ""
echo "📋 Доступные команды:"
echo "  - python manage.py setup_initial_data --clear  # Очистить и загрузить данные"
echo "  - python manage.py setup_initial_data          # Загрузить данные (если пусто)"
echo ""
echo "🌐 Теперь пользователи могут создавать заказы с готовыми странами и фабриками!"
