from __future__ import annotations

from datetime import datetime, time, timedelta

from telegram.error import TelegramError, BadRequest
from telegram.ext import Application, ContextTypes

from app.config import Settings
from app.db import Database
from app.keyboards import plans_keyboard
from app.texts import expired_text


async def delete_message_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    data = context.job.data
    if not data:
        return
    try:
        await context.bot.delete_message(chat_id=data["chat_id"], message_id=data["message_id"])
    except TelegramError:
        pass


async def expire_subscriptions_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    app: Application = context.application
    settings: Settings = app.bot_data["settings"]
    db: Database = app.bot_data["db"]
    now_dt = datetime.now(settings.tz)
    expired = await db.get_expired_active_subscriptions(now_dt)
    for sub in expired:
        try:
            await context.bot.ban_chat_member(settings.group_id, sub.tg_user_id, until_date=now_dt + timedelta(seconds=60))
        except TelegramError:
            pass
        try:
            await context.bot.unban_chat_member(settings.group_id, sub.tg_user_id, only_if_banned=False)
        except TelegramError:
            pass
        try:
            if sub.join_message_chat_id and sub.join_message_id:
                await context.bot.delete_message(chat_id=sub.join_message_chat_id, message_id=sub.join_message_id)
        except TelegramError:
            pass
        await db.mark_expired(sub.tg_user_id)
        try:
            await context.bot.send_message(
                chat_id=sub.user_chat_id,
                text=expired_text(sub.plan_name, sub.access_until.astimezone(settings.tz).strftime("%d.%m.%Y")),
                reply_markup=plans_keyboard(),
            )
        except TelegramError:
            pass



def schedule_jobs(application: Application, settings: Settings) -> None:
    application.job_queue.run_daily(
        expire_subscriptions_job,
        time=time(hour=10, minute=0, tzinfo=settings.tz),
        name="expire_subscriptions",
    )
