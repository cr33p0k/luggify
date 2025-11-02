@echo off
echo Starting Luggify Backend Server...
echo.

REM Активация виртуального окружения
call venv\Scripts\activate.bat

REM Проверка наличия .env файла
if not exist .env (
    echo ERROR: .env file not found!
    echo Please create .env file based on .env.example
    pause
    exit /b 1
)

REM Запуск сервера
echo Starting server on http://localhost:8000
echo Press Ctrl+C to stop
echo.
uvicorn main:app --reload --host 0.0.0.0 --port 8000

pause

