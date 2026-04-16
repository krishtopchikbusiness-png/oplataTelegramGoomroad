# Telegram + Gumroad private group bot

Готовый каркас под Railway:
- Telegram webhook
- Gumroad Ping webhook
- PostgreSQL
- доступ в закрытую группу через join request
- автоматическая ежедневная проверка подписок
- 2 дня ожидания после даты списания

## Структура

- `app/main.py` — веб-приложение FastAPI
- `app/cron_once.py` — отдельный cron-проход для Railway Cron service
- `app/db.py` — таблицы и запросы
- `app/telegram_api.py` — работа с Telegram Bot API
- `app/gumroad.py` — разбор Gumroad webhook и ссылки на checkout
- `app/texts.py` — тексты бота
- `.env.example` — пример переменных

## Как это работает

### Новая покупка
1. Пользователь нажимает `/start`
2. Выбирает тариф
3. Кнопка `Оплатить` ведет на Gumroad checkout
4. В ссылку автоматически подставляется custom field `Telegram ID`
5. Gumroad отправляет Ping на `/gumroad/ping?token=...`
6. Бот сохраняет даты подписки в базу
7. Бот отправляет:
   - сообщение с тарифом и датой
   - сообщение с кнопкой `Войти в группу`
8. Пользователь подает join request
9. Бот одобряет заявку и удаляет только второе сообщение с кнопкой входа

### Продление
- если новый успешный платеж пришел, бот отправляет новое сообщение о продлении

### Неуспешное продление
- в день списания никого не трогаем
- еще 2 дня держим доступ
- если нового платежа нет, бот убирает человека из группы и снова показывает старт с тарифами

## Что нужно создать в Gumroad

Нужно сделать 3 membership-продукта:
- 1 месяц
- 3 месяца
- 12 месяцев

И у каждого добавить custom field с названием `Telegram ID`.

## Как привязать Ping в Gumroad

В Gumroad укажи endpoint:

`https://YOUR_APP_URL/gumroad/ping?token=YOUR_GUMROAD_PING_TOKEN`

## Railway: web service

### Start command

```bash
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

## Railway: cron service

Из этого же репозитория создай второй сервис.

### Start command

```bash
python -m app.cron_once
```

### Cron schedule

Например так:

```text
0 9 * * *
```

Это будет ежедневная проверка в 09:00 по cron.

## Telegram BotFather

После первого запуска webhook выставится автоматически на:

`https://YOUR_APP_URL/telegram/webhook/YOUR_TELEGRAM_WEBHOOK_SECRET`

## Важный момент по смене тарифа

Кнопка `Сменить тариф` в этом каркасе ведет в Gumroad Library,
потому что безопасная смена текущего membership-тарифа нативно делается через `Manage membership` у самого Gumroad.

Если захочешь, это можно потом заменить на другой UX, но такой вариант сейчас самый безопасный и без дубля второй подписки.

## Что нужно выдать боту в группе

Бот должен быть админом группы и иметь права:
- приглашать пользователей
- одобрять join request
- банить / разбанивать участников

## Быстрая проверка

### health

```bash
GET /health
```

### cron endpoint вручную

```bash
curl -X POST \
  -H "Authorization: Bearer YOUR_CRON_SECRET" \
  https://YOUR_APP_URL/cron/check-subscriptions
```
