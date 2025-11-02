# Как применить миграции на Render

## Способ 1: Через Shell (рекомендуется)

1. Откройте Render Dashboard
2. Выберите ваш Web Service
3. Перейдите в раздел "Shell" (вверху страницы)
4. Выполните команды:

```bash
cd server
alembic upgrade head
```

Если видите ошибку про отсутствие модулей, попробуйте:
```bash
pip install -r requirements.txt
cd server
alembic upgrade head
```

## Способ 2: Через Manual Deploy

1. Откройте Render Dashboard → ваш Web Service
2. Нажмите "Manual Deploy" → "Deploy latest commit"
3. Команда `release` из Procfile должна выполниться автоматически

## Проверка

После применения миграций проверьте:
- Откройте https://luggify.onrender.com/health
- Попробуйте создать чеклист через веб-интерфейс

