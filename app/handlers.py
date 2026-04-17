from __future__ import annotations

from datetime import datetime, timedelta

from dateutil.relativedelta import relativedelta
from telegram import ChatJoinRequest, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from app.config import Settings
from app.db import Database
from app.keyboards import (
    admin_request_keyboard,
    join_channel_keyboard,
    open_channel_keyboard,
    plans_keyboard,
    restore_access_keyboard,
    tariff_keyboard,
)
from app.jobs import delete_message_job
from app.texts import (
    PLANS,
    admin_request_text,
    admin_request_result_text,
    already_active_text,
    channel_open_text,
    join_channel_text,
    payment_confirmed_text,
    payment_rejected_text,
    request_sent_text,
    start_text,
    tariff_text,
)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings: Settings = context.application.bot_data["settings"]
    db: Database = context.application.bot_data["db"]
    user = update.effective_user
    chat_id = update.effective_chat.id
    sub = await db.get_subscription(user.id)
    now_dt = datetime.now(settings.tz)
    if sub and sub.status == "active" and sub.access_until > now_dt and not sub.in_chat:
        await update.effective_message.reply_text(
            text=already_active_text(sub.plan_name, sub.access_until.astimezone(settings.tz).strftime("%d.%m.%Y")),
            reply_markup=restore_access_keyboard(),
        )
        return
    await update.effective_message.reply_text(text=start_text(), reply_markup=plans_keyboard())


async def myid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(str(update.effective_user.id))


async def chatid_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.effective_message.reply_text(str(update.effective_chat.id))


async def plans_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()
    settings: Settings = context.application.bot_data["settings"]

    data = query.data or ""
    if data == "back:start":
        await query.message.reply_text(start_text(), reply_markup=plans_keyboard())
        return

    if data.startswith("plan:"):
        plan_code = data.split(":", 1)[1]
        if plan_code not in PLANS:
            return
        await query.message.reply_text(
            text=tariff_text(plan_code, settings.card_number, settings.card_holder),
            reply_markup=tariff_keyboard(plan_code),
        )


async def pay_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()
    data = query.data or ""
    if not data.startswith("pay:"):
        return
    plan_code = data.split(":", 1)[1]
    if plan_code not in PLANS:
        return

    settings: Settings = context.application.bot_data["settings"]
    db: Database = context.application.bot_data["db"]
    user = query.from_user

    existing_request = await db.get_pending_payment_request_by_user(user.id)
    if existing_request:
        await query.message.reply_text(request_sent_text())
        return

    request_id = await db.create_payment_request(
        tg_user_id=user.id,
        tg_username=f"@{user.username}" if user.username else None,
        tg_first_name=user.first_name,
        plan_code=plan_code,
        user_chat_id=query.message.chat_id,
    )

    admin_message = await context.bot.send_message(
        chat_id=settings.admin_id,
        text=admin_request_text(plan_code, f"@{user.username}" if user.username else None, user.id),
        reply_markup=admin_request_keyboard(request_id),
    )
    await db.set_payment_request_admin_message(request_id, admin_message.chat_id, admin_message.message_id)
    await query.message.reply_text(request_sent_text())


async def _create_fresh_join_message(
    *,
    tg_user_id: int,
    chat_id: int,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    settings: Settings = context.application.bot_data["settings"]
    db: Database = context.application.bot_data["db"]
    now_dt = datetime.now(settings.tz)
    invite_link = await context.bot.create_chat_invite_link(
        chat_id=settings.group_id,
        expire_date=now_dt + timedelta(minutes=30),
        creates_join_request=True,
        name=f"join-{tg_user_id}-{int(now_dt.timestamp())}",
    )
    join_message = await context.bot.send_message(
        chat_id=chat_id,
        text=join_channel_text(),
        reply_markup=join_channel_keyboard(invite_link.invite_link),
    )
    await db.set_join_message(tg_user_id, join_message.chat_id, join_message.message_id, invite_link.invite_link)


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()
    data = query.data or ""
    if not data.startswith("admin:"):
        return

    _, action, request_id_str = data.split(":", 2)
    request_id = int(request_id_str)
    db: Database = context.application.bot_data["db"]
    settings: Settings = context.application.bot_data["settings"]

    request = await db.get_payment_request(request_id)
    if not request:
        await query.message.reply_text("Заявка не найдена.")
        return
    if request.status != "pending":
        await query.answer("Эта заявка уже обработана.", show_alert=False)
        return

    if action == "reject":
        await db.mark_payment_request(request_id, "rejected")
        await context.bot.send_message(chat_id=request.user_chat_id, text=payment_rejected_text())
        try:
            await query.edit_message_text(
                text=admin_request_result_text(
                    request.plan_code,
                    request.tg_username,
                    request.tg_user_id,
                    confirmed=False,
                )
            )
        except TelegramError:
            pass
        return

    if action != "approve":
        return

    await db.mark_payment_request(request_id, "confirmed")
    await db.close_other_pending_requests_for_user(request.tg_user_id, request_id)
    months = int(PLANS[request.plan_code]["months"])
    current_sub = await db.get_subscription(request.tg_user_id)
    now_dt = datetime.now(settings.tz)
    base_dt = now_dt
    if current_sub and current_sub.status == "active" and current_sub.access_until > now_dt:
        base_dt = current_sub.access_until.astimezone(settings.tz)
    access_until = base_dt + relativedelta(months=months)

    await db.save_subscription(
        tg_user_id=request.tg_user_id,
        tg_username=request.tg_username,
        tg_first_name=request.tg_first_name,
        plan_code=request.plan_code,
        plan_name=request.plan_name,
        amount_text=request.amount_text,
        access_until=access_until,
        user_chat_id=request.user_chat_id,
    )

    try:
        await context.bot.unban_chat_member(settings.group_id, request.tg_user_id, only_if_banned=False)
    except TelegramError:
        pass

    status_message = await context.bot.send_message(
        chat_id=request.user_chat_id,
        text=payment_confirmed_text(request.plan_name, access_until.strftime("%d.%m.%Y")),
    )
    await db.set_status_message(request.tg_user_id, status_message.chat_id, status_message.message_id)
    await _create_fresh_join_message(
        tg_user_id=request.tg_user_id,
        chat_id=request.user_chat_id,
        context=context,
    )

    try:
        await query.edit_message_text(
            text=admin_request_result_text(
                request.plan_code,
                request.tg_username,
                request.tg_user_id,
                confirmed=True,
            )
        )
    except TelegramError:
        pass


async def restore_access_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    assert query is not None
    await query.answer()
    settings: Settings = context.application.bot_data["settings"]
    db: Database = context.application.bot_data["db"]
    sub = await db.get_subscription(query.from_user.id)
    now_dt = datetime.now(settings.tz)
    if not sub or sub.status != "active" or sub.access_until <= now_dt:
        await query.message.reply_text(start_text(), reply_markup=plans_keyboard())
        return
    await _create_fresh_join_message(tg_user_id=query.from_user.id, chat_id=query.message.chat_id, context=context)


async def join_request_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    join_request: ChatJoinRequest | None = update.chat_join_request
    if join_request is None:
        return
    settings: Settings = context.application.bot_data["settings"]
    db: Database = context.application.bot_data["db"]

    if join_request.chat.id != settings.group_id:
        return

    sub = await db.get_subscription(join_request.from_user.id)
    now_dt = datetime.now(settings.tz)
    if not sub or sub.status != "active" or sub.access_until <= now_dt:
        try:
            await context.bot.decline_chat_join_request(join_request.chat.id, join_request.from_user.id)
        except TelegramError:
            pass
        return

    try:
        await context.bot.approve_chat_join_request(join_request.chat.id, join_request.from_user.id)
    except TelegramError:
        return

    await db.set_in_chat(join_request.from_user.id, True)

    if sub.join_message_chat_id and sub.join_message_id:
        try:
            await context.bot.delete_message(chat_id=sub.join_message_chat_id, message_id=sub.join_message_id)
        except TelegramError:
            pass

    if sub.invite_link:
        try:
            await context.bot.revoke_chat_invite_link(settings.group_id, sub.invite_link)
        except TelegramError:
            pass

    await db.clear_join_message(join_request.from_user.id)

    open_message = await context.bot.send_message(
        chat_id=sub.user_chat_id,
        text=channel_open_text(),
        reply_markup=open_channel_keyboard(settings.channel_url),
    )
    context.job_queue.run_once(
        delete_message_job,
        when=300,
        data={"chat_id": open_message.chat_id, "message_id": open_message.message_id},
        name=f"delete-open-{join_request.from_user.id}-{open_message.message_id}",
    )
