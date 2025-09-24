# Развертывание XXL OrderHub

## Локальная разработка

Для локальной разработки используйте:

```bash
# Запуск с локальными настройками
docker-compose up --build -d
```

Это автоматически использует `docker.env.local` с настройками для локальной разработки:
- `DEBUG=True`
- `SESSION_COOKIE_SECURE=False`
- `CSRF_COOKIE_SECURE=False`
- `BASE_URL=http://localhost:8280`

## Продакшен развертывание

Для продакшена используйте:

```bash
# Запуск с продакшен настройками
docker-compose -f docker-compose.prod.yml up --build -d
```

Это использует `docker.env` с продакшен настройками:
- `DEBUG=False`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `BASE_URL=https://yourdomain.com`

## На сервере

На сервере должен быть файл `docker.env` с продакшен настройками:

```bash
# На сервере
git pull origin main
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up --build -d
```

## Важные файлы

- `docker.env.local` - настройки для локальной разработки
- `docker.env` - настройки для продакшена
- `docker-compose.yml` - конфигурация для локальной разработки
- `docker-compose.prod.yml` - конфигурация для продакшена

## Переменные окружения

### Локальная разработка (docker.env.local)
```
DEBUG=True
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
BASE_URL=http://localhost:8280
```

### Продакшен (docker.env)
```
DEBUG=False
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
BASE_URL=https://yourdomain.com
```
