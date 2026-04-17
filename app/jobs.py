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
        # Сначала отзываем текущую ссылку, чтобы по ней нельзя было войти повторно
        if sub.invite_link:
            try:
                await context.bot.revoke_chat_invite_link(settings.group_id, sub.invite_link)
            except TelegramError:
                pass

        # Если сообщение со вступлением еще висит — удаляем его
        if sub.join_message_chat_id and sub.join_message_id:
            try:
                await context.bot.delete_message(chat_id=sub.join_message_chat_id, message_id=sub.join_message_id)
            except TelegramError:
                pass

        # Баним и НЕ разбаниваем. Разбан только после новой оплаты.
        try:
            await context.bot.ban_chat_member(settings.group_id, sub.tg_user_id)
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
        time(hour=settings.check_hour, minute=settings.check_minute, tzinfo=settings.tz),
        name="expire_subscriptions",
    )
