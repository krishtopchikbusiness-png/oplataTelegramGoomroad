from __future__ import annotations

from datetime import datetime

from telegram.error import TelegramError
from telegram.ext import ContextTypes

from app.db import Database
from app.keyboards import start_keyboard
from app.texts import expired_text



def get_db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.application.bot_data["db"]



def get_settings(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["settings"]


async def expire_subscriptions_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Ежедневная задача.
    В 10:00 по Киеву ищет просроченные подписки и удаляет таких людей из группы.
    """
    db = get_db(context)
    settings = get_settings(context)

    now_dt = datetime.now(settings.tz)
    expired_list = await db.expire_due_subscriptions(now_dt)

    for sub in expired_list:
        # Если пользователь уже в группе, убираем его.
        # Самый простой способ: ban -> сразу unban.
        if sub.is_in_group:
            try:
                await context.bot.ban_chat_member(settings.group_id, sub.tg_user_id)
                await context.bot.unban_chat_member(settings.group_id, sub.tg_user_id, only_if_banned=True)
            except TelegramError:
                pass

        # Если вдруг висело старое сообщение с кнопкой входа — удаляем.
        if sub.join_message_id and sub.last_chat_id:
            try:
                await context.bot.delete_message(sub.last_chat_id, sub.join_message_id)
            except TelegramError:
                pass

        await db.mark_expired(sub.tg_user_id)

        if sub.last_chat_id:
            try:
                await context.bot.send_message(
                    chat_id=sub.last_chat_id,
                    text=expired_text(),
                    reply_markup=start_keyboard(),
                )
            except TelegramError:
                pass
