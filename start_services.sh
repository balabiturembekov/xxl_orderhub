#!/bin/bash

# Скрипт для запуска всех сервисов XXL OrderHub

echo "🚀 Starting XXL OrderHub Services..."

# Переходим в директорию проекта
cd "$(dirname "$0")"

# Активируем виртуальное окружение
source ../env/bin/activate

# Проверяем, что Redis запущен
if ! redis-cli ping > /dev/null 2>&1; then
    echo "❌ Redis is not running. Starting Redis..."
    brew services start redis
    sleep 2
fi

echo "✅ Redis is running"

# Запускаем Django сервер в фоне
echo "🌐 Starting Django server..."
python manage.py runserver 8000 &
DJANGO_PID=$!

# Запускаем Celery worker в фоне
echo "👷 Starting Celery worker..."
celery -A xxl_orderhub worker --loglevel=info &
WORKER_PID=$!

# Запускаем Celery Beat в фоне
echo "⏰ Starting Celery Beat..."
celery -A xxl_orderhub beat --loglevel=info &
BEAT_PID=$!

# Сохраняем PID процессов
echo $DJANGO_PID > django.pid
echo $WORKER_PID > worker.pid
echo $BEAT_PID > beat.pid

echo ""
echo "🎉 All services started successfully!"
echo ""
echo "Services:"
echo "  🌐 Django Server: http://localhost:8000 (PID: $DJANGO_PID)"
echo "  👷 Celery Worker: PID $WORKER_PID"
echo "  ⏰ Celery Beat: PID $BEAT_PID"
echo "  🔴 Redis: localhost:6379"
echo ""
echo "To stop all services, run: ./stop_services.sh"
echo "To check status, run: python manage.py celery_status"
echo ""
echo "Press Ctrl+C to stop this script (services will continue running)"
echo ""

# Ждем сигнала завершения
trap 'echo "Stopping services..."; kill $DJANGO_PID $WORKER_PID $BEAT_PID 2>/dev/null; rm -f *.pid; exit 0' INT

# Ждем завершения
wait
