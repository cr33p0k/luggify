# Render Staging

## Что создать

В Render создай 3 сущности:

1. PostgreSQL
2. Web Service `server`
3. Web Service `client`

## Postgres

Создай базу через:

- `New` -> `Postgres`

Выбери тот же регион, что и для сервисов.

После создания базы возьми `Internal Database URL`.

Официальная документация:

- https://render.com/docs/databases

## Backend service

Создай:

- `New` -> `Web Service`

Настройки:

- Root Directory: `server`
- Environment: `Docker`
- Dockerfile Path: `./Render.dockerfile`

Переменные окружения:

- `DATABASE_URL` = internal database URL из Render Postgres
- `CORS_ALLOWED_ORIGINS` = `http://localhost:5173,http://localhost:5174,https://<client-onrender-domain>`

Опционально:

- `CORS_ALLOWED_ORIGIN_REGEX` = `https://.*\.(vercel\.app|onrender\.com)$`

## Frontend service

Создай:

- `New` -> `Web Service`

Настройки:

- Root Directory: `client`
- Environment: `Docker`
- Dockerfile Path: `./Render.dockerfile`

Build Arg:

- `VITE_API_URL` = `https://<server-onrender-domain>`

Если удобнее, можешь также продублировать как Environment Variable, но для Vite важен именно build-time value.

## Порядок

1. Сначала создай Postgres
2. Потом backend
3. Дождись домена backend
4. Потом frontend c `VITE_API_URL=https://<backend-domain>`
5. После появления домена frontend обнови на backend переменную:
   `CORS_ALLOWED_ORIGINS`

## Где это настраивается в Render

- Root directory:
  Settings -> Build & Deploy -> Root Directory
- Dockerfile path:
  Settings -> Build & Deploy -> Dockerfile Path
- Environment variables:
  Environment

## Важно

- Frontend на Render собирается в production и отдаётся через `serve`
- Backend стартует с миграциями Alembic
- Если поменяешь frontend domain, не забудь обновить `CORS_ALLOWED_ORIGINS` на backend

## Полезные ссылки

- Web services: https://render.com/docs/web-services
- Monorepo root directory: https://render.com/docs/monorepo-support
- Postgres: https://render.com/docs/databases
