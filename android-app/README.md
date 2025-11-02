# Luggify Android App

Android приложение на Jetpack Compose для создания чеклистов для путешествий с учетом погоды.

## Функционал

- ✅ Автозаполнение городов при вводе (с русской поддержкой)
- ✅ Выбор дат поездки через календарь
- ✅ Генерация чеклиста на основе города и дат поездки
- ✅ Отметка вещей в чеклисте (чекбоксы)
- ✅ Добавление и удаление вещей из чеклиста
- ✅ Прогноз погоды для выбранных дат
- ✅ Сохранение состояния чеклиста на сервере
- ✅ Темная тема в стиле Telegram Mini App

## Технологии

- **Jetpack Compose** - современный UI toolkit
- **Material 3** - дизайн система
- **Retrofit** - HTTP клиент для работы с API
- **Navigation Compose** - навигация между экранами
- **ViewModel** - управление состоянием UI
- **Coil** - загрузка изображений прогноза погоды

## Структура проекта

```
app/src/main/java/com/luggify/app/
├── data/
│   ├── api/          # Retrofit API интерфейсы
│   ├── models/       # Модели данных (City, Checklist, DailyForecast)
│   └── repository/    # Repository для работы с данными
├── ui/
│   ├── components/   # Переиспользуемые UI компоненты
│   ├── screens/      # Экраны приложения
│   ├── theme/        # Тема приложения
│   └── viewmodel/    # ViewModel для управления состоянием
└── MainActivity.kt   # Главная Activity
```

## Запуск

1. Откройте проект в Android Studio
2. Дождитесь синхронизации Gradle
3. Подключите Android устройство или запустите эмулятор
4. Нажмите Run

## API Endpoints

Приложение использует следующие эндпоинты:

- `GET /geo/cities-autocomplete?namePrefix=...` - поиск городов
- `POST /generate-packing-list` - генерация чеклиста
- `GET /checklist/{slug}` - получение чеклиста по slug
- `PATCH /checklist/{slug}/state` - обновление состояния чеклиста

Базовая ссылка: `https://luggify.onrender.com/`

