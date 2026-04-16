from datetime import datetime

PLANS = {
    "1m": {"title": "1 месяц", "price": "5 400 грн", "days": 30},
    "3m": {"title": "3 месяца", "price": "8 000 грн", "days": 90},
    "12m": {"title": "12 месяцев", "price": "30 000 грн", "days": 365},
}


def start_text() -> str:
    return "🔐 Доступ к закрытому каналу

Выберите тариф, который вам подходит."


def plan_text(plan_code: str, card_number: str, card_holder: str | None = None) -> str:
    plan = PLANS[plan_code]
    holder_block = f"\nПолучатель: {card_holder}" if card_holder else ""
    return (
        f"🔐 Вы выбрали тариф на {plan['title']}\n\n"
        f"Сумма к оплате: {plan['price']}\n\n"
        f"💳 Карта для оплаты:\n{card_number}{holder_block}\n\n"
        "После оплаты нажмите кнопку «Проверить оплату»."
    )


def admin_request_text(plan_code: str, username: str | None, tg_user_id: int) -> str:
    plan = PLANS[plan_code]
    username_text = f"@{username}" if username else "без username"
    return (
        "📩 Новая заявка на проверку оплаты\n\n"
        f"Тариф: {plan['title']}\n"
        f"Сумма: {plan['price']}\n"
        f"Пользователь: {username_text}\n"
        f"Telegram ID: {tg_user_id}"
    )


def payment_wait_text() -> str:
    return "Заявка отправлена ✅\n\nОжидайте, проверка оплаты обычно занимает 2–5 минут."


def payment_confirmed_text(plan_name: str, access_until: datetime) -> str:
    return (
        "✅ Оплата подтверждена\n\n"
        f"Тариф: {plan_name}\n"
        f"Доступ открыт до: {access_until.strftime('%d.%m.%Y')}"
    )


def join_group_text() -> str:
    return "Для открытия доступа к каналу вам нужно в него вступить.\n\nНажмите кнопку ниже."


def channel_opened_text() -> str:
    return "✅ Доступ в канал открыт"


def payment_rejected_text() -> str:
    return "Оплата пока не подтверждена.\n\nПроверьте, пожалуйста, перевод и попробуйте еще раз."


def expired_text(plan_name: str, access_until: datetime) -> str:
    return (
        "🔐 Срок доступа закончился\n\n"
        f"Ваш тариф: {plan_name}\n"
        f"Доступ был активен до: {access_until.strftime('%d.%m.%Y')}\n\n"
        "Чтобы снова открыть доступ к каналу, выберите подходящий тариф ниже."
    )
