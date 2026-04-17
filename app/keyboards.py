from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup



def plans_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("1 месяц", callback_data="plan:1m")],
            [InlineKeyboardButton("3 месяца", callback_data="plan:3m")],
            [InlineKeyboardButton("12 месяцев", callback_data="plan:12m")],
        ]
    )



def tariff_keyboard(plan_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Проверить оплату", callback_data=f"pay:{plan_code}")],
            [InlineKeyboardButton("Назад", callback_data="back:start")],
        ]
    )



def admin_request_keyboard(request_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Подтвердить оплату", callback_data=f"admin:approve:{request_id}")],
            [InlineKeyboardButton("Не подтвердить", callback_data=f"admin:reject:{request_id}")],
        ]
    )



def join_channel_keyboard(invite_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Вступить в канал", url=invite_url)]]
    )



def open_channel_keyboard(channel_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Перейти в канал", url=channel_url)]]
    )



def restore_access_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Восстановить доступ", callback_data="restore:access")]]
    )
