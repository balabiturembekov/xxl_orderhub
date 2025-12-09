#!/bin/bash

# Скрипт для обновления версии приложения XXL OrderHub
# Использование:
#   ./update_version.sh patch   - увеличить PATCH версию (1.0.0 -> 1.0.1)
#   ./update_version.sh minor   - увеличить MINOR версию (1.0.0 -> 1.1.0)
#   ./update_version.sh major   - увеличить MAJOR версию (1.0.0 -> 2.0.0)
#   ./update_version.sh 1.2.3   - установить конкретную версию

set -e

SETTINGS_FILE="xxl_orderhub/settings.py"

# Проверка существования файла
if [ ! -f "$SETTINGS_FILE" ]; then
    echo "❌ Ошибка: Файл $SETTINGS_FILE не найден!"
    exit 1
fi

# Получение текущей версии
CURRENT_VERSION=$(grep -E "^VERSION = " "$SETTINGS_FILE" | sed "s/VERSION = '\(.*\)'/\1/")

if [ -z "$CURRENT_VERSION" ]; then
    echo "❌ Ошибка: Не удалось найти текущую версию в $SETTINGS_FILE"
    exit 1
fi

echo "📌 Текущая версия: $CURRENT_VERSION"

# Функция для парсинга версии
parse_version() {
    local version=$1
    IFS='.' read -ra PARTS <<< "$version"
    MAJOR=${PARTS[0]}
    MINOR=${PARTS[1]}
    PATCH=${PARTS[2]}
}

# Функция для вычисления новой версии
calculate_new_version() {
    local type=$1
    parse_version "$CURRENT_VERSION"
    
    case $type in
        major)
            NEW_VERSION="$((MAJOR + 1)).0.0"
            ;;
        minor)
            NEW_VERSION="$MAJOR.$((MINOR + 1)).0"
            ;;
        patch)
            NEW_VERSION="$MAJOR.$MINOR.$((PATCH + 1))"
            ;;
        *)
            echo "❌ Ошибка: Неизвестный тип версии: $type"
            echo "Используйте: patch, minor, major или конкретную версию (например, 1.2.3)"
            exit 1
            ;;
    esac
}

# Определение новой версии
if [[ "$1" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    # Конкретная версия указана
    NEW_VERSION=$1
elif [ -n "$1" ]; then
    # Тип версии указан (patch, minor, major)
    calculate_new_version "$1"
else
    echo "❌ Ошибка: Не указан тип версии или конкретная версия"
    echo ""
    echo "Использование:"
    echo "  ./update_version.sh patch   - увеличить PATCH версию (1.0.0 -> 1.0.1)"
    echo "  ./update_version.sh minor   - увеличить MINOR версию (1.0.0 -> 1.1.0)"
    echo "  ./update_version.sh major   - увеличить MAJOR версию (1.0.0 -> 2.0.0)"
    echo "  ./update_version.sh 1.2.3   - установить конкретную версию"
    exit 1
fi

# Проверка, что версия изменилась
if [ "$CURRENT_VERSION" == "$NEW_VERSION" ]; then
    echo "⚠️  Версия уже установлена: $CURRENT_VERSION"
    exit 0
fi

echo "🔄 Обновление версии: $CURRENT_VERSION -> $NEW_VERSION"

# Обновление версии в settings.py
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    sed -i '' "s/VERSION = '$CURRENT_VERSION'/VERSION = '$NEW_VERSION'/" "$SETTINGS_FILE"
else
    # Linux
    sed -i "s/VERSION = '$CURRENT_VERSION'/VERSION = '$NEW_VERSION'/" "$SETTINGS_FILE"
fi

# Проверка успешности обновления
UPDATED_VERSION=$(grep -E "^VERSION = " "$SETTINGS_FILE" | sed "s/VERSION = '\(.*\)'/\1/")

if [ "$UPDATED_VERSION" == "$NEW_VERSION" ]; then
    echo "✅ Версия успешно обновлена до $NEW_VERSION"
    echo ""
    echo "📝 Следующие шаги:"
    echo "   1. Проверьте изменения: git diff $SETTINGS_FILE"
    echo "   2. Закоммитьте изменения: git add $SETTINGS_FILE && git commit -m 'chore: Обновлена версия до $NEW_VERSION'"
    echo "   3. Создайте тег: git tag -a v$NEW_VERSION -m 'Release version $NEW_VERSION'"
    echo "   4. Отправьте изменения: git push origin main --tags"
else
    echo "❌ Ошибка: Не удалось обновить версию"
    exit 1
fi

