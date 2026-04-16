from datetime import datetime

PLANS = {
    "1m": {
        "title": "1 месяц",
        "price": "5 400 грн",
        "days": 30,
    },
    "3m": {
        "title": "3 месяца",
        "price": "8 000 грн",
        "days": 90,
    },
    "12m": {
        "title": "12 месяцев",
        "price": "30 000 грн",
        "days": 365,
    },
}


def start_text() -> str:
    return (
        "🔐 Доступ к закрытому каналу

"
        "Выберите тариф, который вам подходит."
    )



def plan_text(plan_code: str, card_number: str, card_holder: str | None = None) -> str:
    plan = PLANS[plan_code]
    holder_block = ""
    if card_holder:
        holder_block = f"
Получатель: {card_holder}"

    return (
        f"🔐 Вы выбрали тариф на {plan['title']}

"
        f"Сумма к оплате: {plan['price']}

"
        f"💳 Карта для оплаты:
{card_number}{holder_block}

"
        "После оплаты нажмите кнопку «Проверить оплату»."
    )



def admin_request_text(plan_code: str, username: str | None, tg_user_id: int) -> str:
    plan = PLANS[plan_code]
    username_text = f"@{username}" if username else "без username"
    return (
        "📩 Новая заявка на проверку оплаты

"
        f"Тариф: {plan['title']}
"
        f"Сумма: {plan['price']}
"
        f"Пользователь: {username_text}
"
        f"Telegram ID: {tg_user_id}"
    )



def payment_wait_text() -> str:
    return (
        "Заявка отправлена ✅

"
        "Ожидайте, проверка оплаты обычно занимает 2–5 минут."
    )



def payment_confirmed_text(plan_name: str, access_until: datetime) -> str:
    return (
        "✅ Оплата подтверждена

"
        f"Тариф: {plan_name}
"
        f"Доступ открыт до: {access_until.strftime('%d.%m.%Y')}"
    )



def join_group_text() -> str:
    return (
        "Для открытия доступа к каналу вам нужно в него вступить.

"
        "Нажмите кнопку ниже."
    )



def channel_opened_text() -> str:
    return "✅ Доступ в канал открыт"



def payment_rejected_text() -> str:
    return (
        "Оплата пока не подтверждена.

"
        "Проверьте, пожалуйста, перевод и попробуйте еще раз."
    )



def expired_text() -> str:
    return (
        "🔐 Доступ к закрытому каналу

"
        "Срок доступа закончился.

"
        "Выберите тариф, который вам подходит."
    )
