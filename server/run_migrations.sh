#!/bin/bash
# Скрипт для запуска миграций на Render

echo "Запуск миграций Alembic..."
cd server || exit 1

# Проверяем наличие DATABASE_URL
if [ -z "$DATABASE_URL" ]; then
    echo "ERROR: DATABASE_URL не установлен!"
    exit 1
fi

# Запускаем миграции
alembic upgrade head

if [ $? -eq 0 ]; then
    echo "Миграции успешно применены!"
else
    echo "ОШИБКА при применении миграций!"
    exit 1
fi

