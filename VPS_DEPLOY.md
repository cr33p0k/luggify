# Luggify VPS Deploy

Этот вариант поднимает проект как полноценный сайт на своем VPS:

- `example.com` -> frontend
- `api.example.com` -> backend
- PostgreSQL живет в Docker volume на сервере
- HTTPS выпускает и продлевает Caddy автоматически

## Что уже подготовлено

- compose для VPS: `deploy/docker-compose.vps.yml`
- reverse proxy и HTTPS: `deploy/Caddyfile`
- env-шаблон: `deploy/.env.example`
- production frontend image: `client/Prod.dockerfile`

## Что купить

Для начала достаточно VPS класса `2 vCPU / 4 GB RAM`.

Почему не меньше:

- у тебя одновременно будут жить `Postgres`, `FastAPI`, `frontend`, `Caddy`
- еще нужен запас под сборку Docker-образов и обновления

## Что выбрать

Если хочешь максимум цены/качества и сервер ближе к Европе, я бы начал с Hetzner Cloud.
Если хочешь более привычный и "массовый" интерфейс, бери DigitalOcean.

## DNS схема

Создай записи:

- `A` для `example.com` -> IP VPS
- `A` для `api.example.com` -> IP VPS
- `A` или `CNAME` для `www.example.com` -> `example.com`

Если используешь Cloudflare:

- на первом запуске лучше оставить записи в режиме `DNS only`, пока Caddy получает сертификаты

## Подготовка сервера

Пример для Ubuntu 24.04:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker
```

Потом проверь:

```bash
docker --version
docker compose version
```

## Копирование проекта

```bash
git clone <YOUR_REPO_URL>
cd luggify
git checkout render-staging
```

## Настройка env

```bash
cp deploy/.env.example deploy/.env
```

Открой `deploy/.env` и задай свои реальные значения:

- `APP_DOMAIN`
- `APP_WWW_DOMAIN`
- `API_DOMAIN`
- `PUBLIC_API_URL`
- `ACME_EMAIL`
- `POSTGRES_PASSWORD`
- `DATABASE_URL`
- `CORS_ALLOWED_ORIGINS`
- `SECRET_KEY`
- `SMTP_HOST`
- `SMTP_PORT`
- `SMTP_USER`
- `SMTP_PASSWORD`
- `SMTP_FROM`

Важно:

- `DATABASE_URL` должен ссылаться на Docker-сервис `db`, а не на `localhost`
- `CORS_ALLOWED_ORIGINS` должен включать frontend-домены
- `PUBLIC_API_URL` должен быть публичным адресом API, например `https://api.example.com`

## Первый запуск

Из корня проекта:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.vps.yml up -d --build
```

Проверка:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.vps.yml ps
docker compose --env-file deploy/.env -f deploy/docker-compose.vps.yml logs -f caddy
docker compose --env-file deploy/.env -f deploy/docker-compose.vps.yml logs -f server
```

## Обновление проекта

```bash
git pull
docker compose --env-file deploy/.env -f deploy/docker-compose.vps.yml up -d --build
```

## Резервные копии базы

Простой ручной backup:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.vps.yml exec db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" > luggify_backup.sql
```

## Что открыть наружу

На VPS должны быть доступны только:

- `80/tcp`
- `443/tcp`
- `22/tcp` для SSH

`5432` наружу не открывай.

## Полезные команды

Остановить:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.vps.yml down
```

Пересобрать с нуля:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.vps.yml up -d --build --force-recreate
```

Посмотреть логи:

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.vps.yml logs -f
```
