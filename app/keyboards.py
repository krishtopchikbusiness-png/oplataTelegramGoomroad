from telegram import InlineKeyboardButton, InlineKeyboardMarkup



def start_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("1 месяц", callback_data="plan:1m")],
            [InlineKeyboardButton("3 месяца", callback_data="plan:3m")],
            [InlineKeyboardButton("12 месяцев", callback_data="plan:12m")],
        ]
    )



def plan_keyboard(plan_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Проверить оплату", callback_data=f"verify:{plan_code}")],
            [InlineKeyboardButton("Назад", callback_data="back:start")],
        ]
    )



def admin_review_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Подтвердить оплату", callback_data=f"admin:approve:{request_id}")],
            [InlineKeyboardButton("Не подтвердить", callback_data=f"admin:reject:{request_id}")],
        ]
    )



def join_group_keyboard(invite_link: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Вступить в канал", url=invite_link)]]
    )



def open_channel_keyboard(channel_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Перейти в канал", url=channel_url)]]
    )
