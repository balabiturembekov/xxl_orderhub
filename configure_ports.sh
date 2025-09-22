#!/bin/bash

# Скрипт для настройки портов XXL OrderHub
# Использование: ./configure_ports.sh [порт]

set -e

# Порт по умолчанию
DEFAULT_PORT=8080
PORT=${1:-$DEFAULT_PORT}

echo "🔧 Настройка портов для XXL OrderHub..."

# Проверяем, что порт свободен
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "❌ Порт $PORT уже занят!"
    echo "📋 Занятые порты:"
    lsof -i :$PORT
    echo ""
    echo "💡 Попробуйте другой порт:"
    echo "   ./configure_ports.sh 8081"
    echo "   ./configure_ports.sh 9000"
    echo "   ./configure_ports.sh 3000"
    exit 1
fi

echo "✅ Порт $PORT свободен"

# Обновляем docker-compose.yml
echo "📝 Обновляем docker-compose.yml..."
sed -i.bak "s/- \"[0-9]*:80\"/- \"$PORT:80\"/" docker-compose.yml

# Обновляем deploy.sh
echo "📝 Обновляем deploy.sh..."
sed -i.bak "s/localhost:[0-9]*/localhost:$PORT/g" deploy.sh

# Обновляем README.md
echo "📝 Обновляем README.md..."
sed -i.bak "s/localhost:[0-9]*/localhost:$PORT/g" README.md

echo "✅ Конфигурация обновлена для порта $PORT"
echo ""
echo "🚀 Теперь можете запустить:"
echo "   ./deploy.sh"
echo ""
echo "🌐 Приложение будет доступно по адресу:"
echo "   http://localhost:$PORT/"
echo "   http://localhost:$PORT/flower/ (логин: admin, пароль: admin123)"
