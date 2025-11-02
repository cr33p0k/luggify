# Luggify Backend

FastAPI сервер для генерации списков вещей для путешествий.

## Требования

- Python 3.9+
- PostgreSQL база данных
- API ключ OpenWeatherMap

## Установка и запуск

### 1. Перейдите в папку server

```bash
cd server
```

### 2. Активируйте виртуальное окружение

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. Установите зависимости (если еще не установлены)

```bash
pip install -r requirements.txt
```

### 4. Создайте файл .env

Создайте файл `.env` в папке `server` со следующим содержимым:

```env
OPENWEATHER_API_KEY=ваш_ключ_openweather
DATABASE_URL=postgresql+asyncpg://пользователь:пароль@хост:порт/база_данных
```

**Пример для локальной PostgreSQL:**
```env
OPENWEATHER_API_KEY=1234567890abcdef1234567890abcdef
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/luggify
```

### 5. Инициализируйте базу данных (если еще не инициализирована)

```bash
alembic upgrade head
```

Если база данных пустая, можно также запустить:
```bash
python init_db.py
```

### 6. Запустите сервер

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Или просто:
```bash
uvicorn main:app --reload
```

Сервер будет доступен по адресу: `http://localhost:8000`

### 7. Проверьте работу сервера

Откройте в браузере:
- API документация: http://localhost:8000/docs
- Альтернативная документация: http://localhost:8000/redoc
- Корневой endpoint: http://localhost:8000/

## Основные endpoints

- `GET /` - проверка работы сервера
- `GET /geo/cities-autocomplete?namePrefix=...` - поиск городов
- `POST /generate-packing-list` - генерация списка вещей
- `GET /checklist/{slug}` - получение чеклиста по slug
- `PATCH /checklist/{slug}/state` - обновление состояния чеклиста

## Получение API ключа OpenWeatherMap

1. Зарегистрируйтесь на https://openweathermap.org/api
2. Получите бесплатный API ключ
3. Добавьте его в файл `.env`

## Troubleshooting

### Ошибка "DATABASE_URL is not set!"
- Убедитесь, что файл `.env` существует в папке `server`
- Проверьте, что в `.env` указан правильный `DATABASE_URL`

### Ошибка "Не найден ключ OPENWEATHER_API_KEY"
- Проверьте, что в `.env` указан `OPENWEATHER_API_KEY`

### Ошибка подключения к базе данных
- Убедитесь, что PostgreSQL запущен
- Проверьте правильность данных подключения в `DATABASE_URL`
- Убедитесь, что база данных существует

### Порт 8000 занят
- Используйте другой порт: `uvicorn main:app --reload --port 8001`

