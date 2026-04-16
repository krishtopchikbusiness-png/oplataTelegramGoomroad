from __future__ import annotations

from datetime import datetime, timedelta

from telegram import ChatJoinRequest, InlineKeyboardMarkup, Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from app.db import Database
from app.keyboards import admin_review_keyboard, join_group_keyboard, plan_keyboard, start_keyboard
from app.texts import (
    PLANS,
    admin_request_text,
    join_group_text,
    payment_confirmed_text,
    payment_rejected_text,
    plan_text,
    start_text,
)


# =========================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# =========================

def get_db(context: ContextTypes.DEFAULT_TYPE) -> Database:
    return context.application.bot_data["db"]



def get_settings(context: ContextTypes.DEFAULT_TYPE):
    return context.application.bot_data["settings"]


# =========================
# ПОЛЕЗНЫЕ КОМАНДЫ ДЛЯ ТЕСТА
# =========================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message:
        return
    await update.effective_message.reply_text(
        text=start_text(),
        reply_markup=start_keyboard(),
    )


async def myid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_user:
        return
    await update.effective_message.reply_text(f"Ваш Telegram ID: {update.effective_user.id}")


async def chatid_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.effective_message or not update.effective_chat:
        return
    await update.effective_message.reply_text(f"ID этого чата: {update.effective_chat.id}")


# =========================
# CALLBACK-КНОПКИ ПОЛЬЗОВАТЕЛЯ
# =========================
async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    data = query.data or ""

    if data.startswith("plan:"):
        await open_plan(update, context)
        return

    if data == "back:start":
        await query.answer()
        await query.edit_message_text(
            text=start_text(),
            reply_markup=start_keyboard(),
        )
        return

    if data.startswith("verify:"):
        await verify_payment(update, context)
        return

    if data.startswith("admin:"):
        await admin_action(update, context)
        return

    await query.answer()


async def open_plan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if not query:
        return

    settings = get_settings(context)
    plan_code = (query.data or "").split(":", 1)[1]

    await query.answer()
    await query.edit_message_text(
        text=plan_text(plan_code, settings.card_number, settings.card_holder or None),
        reply_markup=plan_keyboard(plan_code),
    )


async def verify_payment(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    chat = update.effective_chat

    if not query or not user or not chat:
        return

    db = get_db(context)
    settings = get_settings(context)

    plan_code = (query.data or "").split(":", 1)[1]

    request_id = await db.create_payment_request(
        tg_user_id=user.id,
        tg_username=user.username,
        tg_first_name=user.first_name,
        plan_code=plan_code,
        user_chat_id=chat.id,
    )

    admin_message = await context.bot.send_message(
        chat_id=settings.admin_id,
        text=admin_request_text(plan_code, user.username, user.id),
        reply_markup=admin_review_keyboard(request_id),
    )

    await db.set_payment_request_admin_message(
        request_id=request_id,
        admin_chat_id=admin_message.chat_id,
        admin_message_id=admin_message.message_id,
    )

    await query.answer("Заявка отправлена админу")


# =========================
# CALLBACK-КНОПКИ АДМИНА
# =========================
async def admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if not query or not user:
        return

    settings = get_settings(context)
    if user.id != settings.admin_id:
        await query.answer("Эта кнопка только для админа", show_alert=True)
        return

    parts = (query.data or "").split(":")
    if len(parts) != 3:
        await query.answer()
        return

    action = parts[1]
    request_id = int(parts[2])

    db = get_db(context)
    payment_request = await db.get_payment_request(request_id)
    if not payment_request:
        await query.answer("Заявка не найдена", show_alert=True)
        return

    if payment_request.status != "pending":
        await query.answer("Эта заявка уже обработана", show_alert=True)
        return

    if action == "approve":
        await approve_payment(update, context, payment_request)
        return

    if action == "reject":
        await reject_payment(update, context, payment_request)
        return

    await query.answer()


async def approve_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_request) -> None:
    query = update.callback_query
    if not query:
        return

    db = get_db(context)
    settings = get_settings(context)

    now_dt = datetime.now(settings.tz)
    access_until = now_dt + timedelta(days=PLANS[payment_request.plan_code]["days"])

    # Создаем отдельную ссылку для вступления по заявке.
    invite = await context.bot.create_chat_invite_link(
        chat_id=settings.group_id,
        name=f"join_{payment_request.tg_user_id}_{int(now_dt.timestamp())}",
        creates_join_request=True,
    )

    status_msg = await context.bot.send_message(
        chat_id=payment_request.user_chat_id,
        text=payment_confirmed_text(payment_request.plan_name, access_until),
    )
    join_msg = await context.bot.send_message(
        chat_id=payment_request.user_chat_id,
        text=join_group_text(),
        reply_markup=join_group_keyboard(invite.invite_link),
    )

    await db.upsert_subscription(
        tg_user_id=payment_request.tg_user_id,
        tg_username=payment_request.tg_username,
        tg_first_name=payment_request.tg_first_name,
        plan_code=payment_request.plan_code,
        access_until=access_until,
        last_chat_id=payment_request.user_chat_id,
        status_message_id=status_msg.message_id,
        join_message_id=join_msg.message_id,
        invite_link=invite.invite_link,
    )
    await db.update_payment_request_status(payment_request.id, "approved")

    await query.answer("Оплата подтверждена")
    await query.edit_message_text(
        text=(query.message.text_html if query.message and query.message.text_html else query.message.text if query.message else "")
        + "\n\n✅ Оплата подтверждена"
    )


async def reject_payment(update: Update, context: ContextTypes.DEFAULT_TYPE, payment_request) -> None:
    query = update.callback_query
    if not query:
        return

    db = get_db(context)
    await db.update_payment_request_status(payment_request.id, "rejected")

    await context.bot.send_message(
        chat_id=payment_request.user_chat_id,
        text=payment_rejected_text(),
        reply_markup=plan_keyboard(payment_request.plan_code),
    )

    await query.answer("Заявка отклонена")
    await query.edit_message_text(
        text=(query.message.text_html if query.message and query.message.text_html else query.message.text if query.message else "")
        + "\n\n❌ Оплата не подтверждена"
    )


# =========================
# ЗАЯВКА В ГРУППУ
# =========================
async def on_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    join_request: ChatJoinRequest | None = update.chat_join_request
    if not join_request:
        return

    db = get_db(context)
    settings = get_settings(context)

    subscription = await db.get_subscription(join_request.from_user.id)
    if not subscription:
        await context.bot.decline_chat_join_request(settings.group_id, join_request.from_user.id)
        return

    # Дополнительная защита: одобряем только если invite link совпадает.
    request_invite = join_request.invite_link.invite_link if join_request.invite_link else None
    if subscription.status != "active" or not subscription.last_invite_link or request_invite != subscription.last_invite_link:
        await context.bot.decline_chat_join_request(settings.group_id, join_request.from_user.id)
        return

    await context.bot.approve_chat_join_request(settings.group_id, join_request.from_user.id)

    # Ссылку сразу отзываем, чтобы не использовать повторно.
    try:
        await context.bot.revoke_chat_invite_link(settings.group_id, subscription.last_invite_link)
    except TelegramError:
        pass

    # Удаляем только второе сообщение с кнопкой входа.
    if subscription.join_message_id and subscription.last_chat_id:
        try:
            await context.bot.delete_message(subscription.last_chat_id, subscription.join_message_id)
        except TelegramError:
            pass

    await db.mark_joined(join_request.from_user.id)

    # Сразу возвращаем стартовое меню, как ты и хотел.
    if subscription.last_chat_id:
        await context.bot.send_message(
            chat_id=subscription.last_chat_id,
            text=start_text(),
            reply_markup=start_keyboard(),
        )
