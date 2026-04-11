# Telegram Bot

## Что уже умеет

- Авторизовывать Telegram-пользователя по `tg_id` в базе
- Показывать ближайшую поездку
- Давать выбрать конкретную поездку, с которой бот будет работать по умолчанию
- Показывать `/whoami` со своим `tg_id`, привязкой аккаунта и числом видимых поездок
- Подсказывать, что ещё не собрано
- Отвечать через AI по ближайшей поездке
- Выполнять AI-команды над чеклистом:
  - `добавь powerbank`
  - `удали фен`
  - `отметь паспорт и зарядку`
  - `в поездке в Стамбул удали фен`
  - `сними отметку с аптечки`
- Подтверждать рискованные действия кнопками `Да` / `Нет` перед удалением вещей
- Если поездок в одном городе несколько, просить выбрать нужную поездку кнопкой

## Что нужно указать в `.env`

```env
TELEGRAM_BOT_TOKEN=your_bot_token
GEMINI_API_KEY=your_gemini_api_key
TELEGRAM_MINI_APP_URL=https://your-public-mini-app-url
TELEGRAM_AUTH_MAX_AGE=86400
ALLOW_INSECURE_TELEGRAM_AUTH=false
```

`TELEGRAM_MINI_APP_URL` можно временно не задавать. Тогда кнопка открытия mini app просто не появится.

## Как подключить именно `@luggify_bot`

1. Открой в Telegram `@BotFather`.
2. Если токена у тебя ещё нет, используй `/mybots` -> выбери `@luggify_bot` -> `API Token`.
3. Скопируй токен и добавь его в корневой `.env` проекта:

```env
TELEGRAM_BOT_TOKEN=123456:your_real_token
```

4. Если хочешь сразу проверять AI-ответы, добавь ещё:

```env
GEMINI_API_KEY=your_gemini_api_key
```

5. Если mini app пока не нужен, `TELEGRAM_MINI_APP_URL` можно оставить пустым.

## Как запустить через Docker

Только базовые сервисы:

```bash
docker compose up -d
```

С ботом:

```bash
docker compose --profile telegram up -d --build telegram-bot
```

Если хочешь поднять всё сразу, включая бота:

```bash
docker compose --profile telegram up -d --build
```

Логи бота:

```bash
docker compose --profile telegram logs -f telegram-bot
```

Полная пересборка бота после изменений:

```bash
docker compose --profile telegram up -d --build --force-recreate telegram-bot
```

Остановить только бота:

```bash
docker compose --profile telegram stop telegram-bot
```

Проверить, что бот действительно стартовал:

```bash
docker compose --profile telegram ps telegram-bot
docker compose --profile telegram logs -f telegram-bot
```

В логах не должно быть ошибок про `TELEGRAM_BOT_TOKEN`.

## Как протестировать руками

1. Запусти backend и базу:

```bash
docker compose up -d
```

2. Запусти бота:

```bash
docker compose --profile telegram up -d --build telegram-bot
```

3. Открой в Telegram `@luggify_bot` и нажми `Start`.
4. Убедись, что у тебя уже есть хотя бы один чеклист в локальной базе.
5. Проверь сценарии:
   - `/trip`
   - `/forgot`
   - `/choose`
   - `/whoami`
   - `/ai`
   - `добавь powerbank`
   - `удали фен`

Если у тебя две поездки в один город, попробуй так:

- `в поездке в Стамбул удали фен`
- бот должен не гадать, а показать выбор нужной поездки
- после выбора, если действие рискованное, придёт подтверждение `Да / Нет`

Если `/whoami` показывает `Связанный пользователь: не найден`, а поездки в вебе у тебя есть, для локальной разработки можно разово привязать существующий аккаунт вручную:

```bash
docker compose exec db psql -U luggify -d luggify_db -c "update users set tg_id='ТВОЙ_TELEGRAM_ID' where email='ТВОЙ_EMAIL';"
```

После этого перезапускать бота не нужно, можно просто снова отправить `/trip`.

## Локальные замечания

- Сам бот через long polling может работать локально без публичного сервера.
- Mini app для Telegram обычно требует публичный `https` URL, поэтому для кнопки mini app на этапе локальной разработки удобнее использовать staging или tunnel.
