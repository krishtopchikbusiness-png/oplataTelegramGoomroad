from __future__ import annotations

PLANS = {
    "1m": {"name": "1 месяц", "amount": "5 400 грн", "months": 1},
    "3m": {"name": "3 месяца", "amount": "8 000 грн", "months": 3},
    "12m": {"name": "12 месяцев", "amount": "30 000 грн", "months": 12},
}



def start_text() -> str:
    return "🔐 Доступ к закрытому каналу\n\nВыберите тариф, который вам подходит."



def tariff_text(plan_code: str, card_number: str, card_holder: str) -> str:
    plan = PLANS[plan_code]
    holder = f"\nПолучатель: {card_holder}" if card_holder else ""
    return (
        f"🔐 Вы выбрали тариф на {plan['name']}\n\n"
        f"Сумма к оплате: {plan['amount']}\n\n"
        f"💳 Карта для оплаты:\n{card_number}{holder}\n\n"
        f"После оплаты нажмите кнопку «Проверить оплату»."
    )



def request_sent_text() -> str:
    return "Заявка отправлена ✅\n\nОжидайте, проверка оплаты обычно занимает 2–5 минут."



def admin_request_text(plan_code: str, username: str | None, tg_user_id: int) -> str:
    plan = PLANS[plan_code]
    username_text = username if username else "без username"
    return (
        "📩 Новая заявка на проверку оплаты\n\n"
        f"Тариф: {plan['name']}\n"
        f"Сумма: {plan['amount']}\n"
        f"Пользователь: {username_text}\n"
        f"Telegram ID: {tg_user_id}"
    )



def payment_confirmed_text(plan_name: str, access_until_str: str) -> str:
    return (
        "✅ Оплата подтверждена\n\n"
        f"Тариф: {plan_name}\n"
        f"Доступ открыт до: {access_until_str}"
    )



def join_channel_text() -> str:
    return (
        "Для открытия доступа к каналу вам нужно в него вступить.\n\n"
        "Нажмите кнопку ниже."
    )



def channel_open_text() -> str:
    return "✅ Доступ в канал открыт"



def payment_rejected_text() -> str:
    return (
        "Оплата пока не подтверждена.\n\n"
        "Проверьте, пожалуйста, перевод и попробуйте еще раз."
    )



def expired_text(plan_name: str, access_until_str: str) -> str:
    return (
        "🔐 Срок доступа закончился\n\n"
        f"Ваш тариф: {plan_name}\n"
        f"Доступ был активен до: {access_until_str}\n\n"
        "Чтобы снова открыть доступ к каналу, выберите подходящий тариф ниже."
    )



def already_active_text(plan_name: str, access_until_str: str) -> str:
    return (
        "✅ У вас уже есть активный доступ\n\n"
        f"Тариф: {plan_name}\n"
        f"Доступ открыт до: {access_until_str}\n\n"
        "Если нужно снова войти в канал, нажмите кнопку ниже."
    )
