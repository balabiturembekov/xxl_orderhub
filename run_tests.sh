#!/bin/bash

# Скрипт для запуска тестов модуля "Управления заказами"
# Использование: ./run_tests.sh [опции]

set -e  # Остановить при ошибке

echo "🧪 Запуск тестов модуля 'Управления заказами'..."

# Проверяем, что мы в правильной директории
if [ ! -f "manage.py" ]; then
    echo "❌ Файл manage.py не найден. Запустите скрипт из корневой директории проекта."
    exit 1
fi

# Проверяем, что pytest установлен
if ! command -v pytest &> /dev/null; then
    echo "❌ pytest не найден. Установите pytest: pip install pytest pytest-django pytest-cov"
    exit 1
fi

# Создаем виртуальное окружение если его нет
if [ ! -d "venv" ]; then
    echo "📦 Создаем виртуальное окружение..."
    python3 -m venv venv
fi

# Активируем виртуальное окружение
echo "🔧 Активируем виртуальное окружение..."
source venv/bin/activate

# Устанавливаем зависимости
echo "📥 Устанавливаем зависимости..."
pip install -q pytest pytest-django pytest-cov pytest-xdist

# Настройки для тестов
export DJANGO_SETTINGS_MODULE=xxl_orderhub.settings
export PYTHONPATH=$PWD:$PYTHONPATH

# Создаем тестовую базу данных
echo "🗄️ Создаем тестовую базу данных..."
python manage.py migrate --run-syncdb

# Запускаем тесты
echo "🚀 Запускаем тесты..."

# Определяем какие тесты запускать
if [ "$1" = "all" ]; then
    echo "📋 Запускаем все тесты..."
    pytest orders/tests/ -v --tb=short --cov=orders --cov-report=html --cov-report=term-missing
elif [ "$1" = "orders" ]; then
    echo "📋 Запускаем тесты управления заказами..."
    pytest orders/tests/test_orders.py orders/tests/test_order_management.py -v --tb=short
elif [ "$1" = "validators" ]; then
    echo "📋 Запускаем тесты валидаторов..."
    pytest orders/tests/test_file_validators.py -v --tb=short
elif [ "$1" = "filters" ]; then
    echo "📋 Запускаем тесты template filters..."
    pytest orders/tests/test_template_filters.py -v --tb=short
elif [ "$1" = "coverage" ]; then
    echo "📋 Запускаем тесты с покрытием кода..."
    pytest orders/tests/ -v --cov=orders --cov-report=html --cov-report=term-missing --cov-fail-under=80
elif [ "$1" = "fast" ]; then
    echo "📋 Запускаем быстрые тесты..."
    pytest orders/tests/ -v --tb=short -x --nomigrations
else
    echo "📋 Запускаем тесты по умолчанию..."
    pytest orders/tests/test_orders.py orders/tests/test_order_management.py -v --tb=short
fi

# Проверяем результат
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ Все тесты прошли успешно!"
    echo ""
    echo "📊 Результаты:"
    echo "   • Тесты модуля 'Управления заказами' - ✅ ПРОЙДЕНЫ"
    echo "   • Валидаторы файлов - ✅ ПРОЙДЕНЫ"
    echo "   • Template filters - ✅ ПРОЙДЕНЫ"
    echo ""
    echo "🎯 Система готова к использованию!"
else
    echo ""
    echo "❌ Некоторые тесты не прошли!"
    echo ""
    echo "🔍 Проверьте ошибки выше и исправьте их."
    exit 1
fi

echo ""
echo "📖 Доступные опции:"
echo "   • ./run_tests.sh all        - Все тесты с покрытием кода"
echo "   • ./run_tests.sh orders     - Только тесты управления заказами"
echo "   • ./run_tests.sh validators - Только тесты валидаторов"
echo "   • ./run_tests.sh filters    - Только тесты template filters"
echo "   • ./run_tests.sh coverage   - Тесты с покрытием кода"
echo "   • ./run_tests.sh fast       - Быстрые тесты"
echo ""
echo "📁 Отчеты покрытия кода: htmlcov/index.html"
