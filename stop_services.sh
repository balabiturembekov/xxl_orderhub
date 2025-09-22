#!/bin/bash

# Скрипт для остановки всех сервисов XXL OrderHub

echo "🛑 Stopping XXL OrderHub Services..."

# Переходим в директорию проекта
cd "$(dirname "$0")"

# Останавливаем процессы по PID файлам
if [ -f django.pid ]; then
    DJANGO_PID=$(cat django.pid)
    if kill -0 $DJANGO_PID 2>/dev/null; then
        echo "🌐 Stopping Django server (PID: $DJANGO_PID)..."
        kill $DJANGO_PID
    fi
    rm -f django.pid
fi

if [ -f worker.pid ]; then
    WORKER_PID=$(cat worker.pid)
    if kill -0 $WORKER_PID 2>/dev/null; then
        echo "👷 Stopping Celery worker (PID: $WORKER_PID)..."
        kill $WORKER_PID
    fi
    rm -f worker.pid
fi

if [ -f beat.pid ]; then
    BEAT_PID=$(cat beat.pid)
    if kill -0 $BEAT_PID 2>/dev/null; then
        echo "⏰ Stopping Celery Beat (PID: $BEAT_PID)..."
        kill $BEAT_PID
    fi
    rm -f beat.pid
fi

# Дополнительная очистка процессов
echo "🧹 Cleaning up remaining processes..."
pkill -f "python manage.py runserver"
pkill -f "celery.*worker"
pkill -f "celery.*beat"

echo "✅ All services stopped"
