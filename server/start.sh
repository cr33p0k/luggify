#!/bin/bash

echo "Starting Luggify Backend Server..."
echo ""

# Активация виртуального окружения
source venv/bin/activate

# Проверка наличия общего .env файла в корне проекта
if [ ! -f ../.env ]; then
    echo "ERROR: ../.env file not found!"
    echo "Please create the project root .env based on .env.example"
    exit 1
fi

# Запуск сервера
echo "Starting server on http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""
uvicorn main:app --reload --host 0.0.0.0 --port 8000
