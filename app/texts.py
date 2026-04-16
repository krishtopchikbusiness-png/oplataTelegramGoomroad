from datetime import datetime
from zoneinfo import ZoneInfo

PLAN_META = {
    "1m": {
        "title": "1 месяц",
        "price": "8 000 грн",
        "renewal": "каждые 30 дней",
    },
    "3m": {
        "title": "3 месяца",
        "price": "5 400 грн",
        "renewal": "каждые 3 месяца",
    },
    "12m": {
        "title": "12 месяцев",
        "price": "30 000 грн",
        "renewal": "каждые 12 месяцев",
    },
}


def fmt_dt(dt: datetime | None, tz_name: str) -> str:
    if not dt:
        return "—"
    return dt.astimezone(ZoneInfo(tz_name)).strftime("%d.%m.%Y")


def start_text() -> str:
    return (
        "🔐 Доступ к закрытой группе\n\n"
        "Выберите подходящий тариф ниже.\n\n"
        "1 месяц — 8 000 грн\n"
        "3 месяца — 5 400 грн\n"
        "12 месяцев — 30 000 грн\n\n"
        "Подписка продлевается автоматически по выбранному тарифу.\n"
        "Следующее списание происходит в дату оформления подписки."
    )


def plan_text(plan_code: str) -> str:
    meta = PLAN_META[plan_code]
    return (
        f"🔐 {meta['title']}\n\n"
        f"Стоимость: {meta['price']}\n\n"
        "Подписка продлевается автоматически.\n"
        f"Продление: {meta['renewal']}."
    )


def payment_success_text(plan_code: str, access_until: datetime, next_billing_at: datetime, tz_name: str) -> str:
    meta = PLAN_META[plan_code]
    return (
        "✅ Оплата прошла успешно\n\n"
        f"Тариф: {meta['title']}\n"
        f"Доступ активен до: {fmt_dt(access_until, tz_name)}\n"
        f"Следующее автоматическое списание: {fmt_dt(next_billing_at, tz_name)}"
    )


def join_prompt_text() -> str:
    return "Нажмите кнопку ниже, чтобы присоединиться к группе."


def renewed_text(plan_code: str, access_until: datetime, next_billing_at: datetime, tz_name: str) -> str:
    meta = PLAN_META[plan_code]
    return (
        "✅ Подписка успешно продлена\n\n"
        f"Тариф: {meta['title']}\n"
        f"Доступ активен до: {fmt_dt(access_until, tz_name)}\n"
        f"Следующее автоматическое списание: {fmt_dt(next_billing_at, tz_name)}"
    )


def active_text(plan_code: str, access_until: datetime, next_billing_at: datetime, tz_name: str) -> str:
    meta = PLAN_META[plan_code]
    return (
        "🔐 Подписка активна\n\n"
        f"Тариф: {meta['title']}\n"
        f"Доступ активен до: {fmt_dt(access_until, tz_name)}\n"
        f"Следующее автоматическое списание: {fmt_dt(next_billing_at, tz_name)}"
    )


def change_tariff_text() -> str:
    return (
        "Сменить тариф можно через вашу подписку в Gumroad.\n\n"
        "Откройте библиотеку Gumroad, выберите свою подписку и нажмите Manage membership."
    )
