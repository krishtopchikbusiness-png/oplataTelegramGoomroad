from __future__ import annotations

from datetime import timedelta

from app import db
from app.config import Settings
from app.gumroad import gumroad_url_for_plan
from app.telegram_api import TelegramAPI, inline_keyboard, callback_button, url_button
from app.texts import (
    active_text,
    change_tariff_text,
    join_prompt_text,
    payment_success_text,
    plan_text,
    renewed_text,
    start_text,
)


def start_keyboard() -> dict:
    return inline_keyboard(
        [
            [callback_button("1 месяц", "plan:1m")],
            [callback_button("3 месяца", "plan:3m")],
            [callback_button("12 месяцев", "plan:12m")],
        ]
    )


def plan_keyboard(plan_code: str, checkout_url: str) -> dict:
    return inline_keyboard(
        [
            [url_button("Оплатить", checkout_url)],
            [callback_button("Назад", "home")],
        ]
    )


def active_keyboard(in_group: bool) -> dict:
    rows = []
    if not in_group:
        rows.append([callback_button("Войти в группу", "join")])
    rows.append([callback_button("Сменить тариф", "change_tariff")])
    return inline_keyboard(rows)


def change_tariff_keyboard(settings: Settings) -> dict:
    return inline_keyboard(
        [
            [url_button("Открыть Gumroad Library", settings.gumroad_library_url)],
            [callback_button("Назад", "home")],
        ]
    )


async def render_home_for_user(tg: TelegramAPI, settings: Settings, chat_id: int, message_id: int | None, tg_user_id: int):
    sub = db.get_subscription(settings.database_url, tg_user_id)
    if sub and sub.get("status") in {"active", "grace"} and sub.get("access_until") and sub.get("next_billing_at"):
        text = active_text(sub["plan_code"], sub["access_until"], sub["next_billing_at"], settings.app_timezone)
        markup = active_keyboard(bool(sub.get("is_in_group")))
    else:
        text = start_text()
        markup = start_keyboard()

    if message_id:
        return await tg.edit_message_text(chat_id, message_id, text, markup)
    return await tg.send_message(chat_id, text, markup)


async def render_plan_screen(tg: TelegramAPI, settings: Settings, chat_id: int, message_id: int, tg_user_id: int, plan_code: str):
    checkout_url = gumroad_url_for_plan(settings, plan_code, tg_user_id)
    return await tg.edit_message_text(chat_id, message_id, plan_text(plan_code), plan_keyboard(plan_code, checkout_url))


async def send_success_flow(tg: TelegramAPI, settings: Settings, tg_user_id: int, first_payment: bool):
    sub = db.get_subscription(settings.database_url, tg_user_id)
    if not sub:
        return

    chat_id = int(sub.get("last_chat_id") or tg_user_id)
    await tg.unban_chat_member(settings.group_id, tg_user_id)

    status_text = payment_success_text(
        sub["plan_code"], sub["access_until"], sub["next_billing_at"], settings.app_timezone
    ) if first_payment or not sub.get("is_in_group") else renewed_text(
        sub["plan_code"], sub["access_until"], sub["next_billing_at"], settings.app_timezone
    )

    status_msg = await tg.send_message(chat_id, status_text, active_keyboard(bool(sub.get("is_in_group"))))
    db.set_status_message_id(settings.database_url, tg_user_id, status_msg["message_id"], chat_id)

    if not sub.get("is_in_group"):
        if sub.get("last_invite_link"):
            try:
                await tg.revoke_invite_link(settings.group_id, sub["last_invite_link"])
            except Exception:
                pass
        invite_link = await tg.create_join_request_link(settings.group_id, f"join-{tg_user_id}")
        join_msg = await tg.send_message(
            chat_id,
            join_prompt_text(),
            inline_keyboard([[url_button("Войти в группу", invite_link)]]),
        )
        db.set_join_message(settings.database_url, tg_user_id, join_msg["message_id"], invite_link, chat_id)


async def resend_join_flow(tg: TelegramAPI, settings: Settings, tg_user_id: int):
    sub = db.get_subscription(settings.database_url, tg_user_id)
    if not sub:
        return
    chat_id = int(sub.get("last_chat_id") or tg_user_id)
    if sub.get("last_invite_link"):
        try:
            await tg.revoke_invite_link(settings.group_id, sub["last_invite_link"])
        except Exception:
            pass
    invite_link = await tg.create_join_request_link(settings.group_id, f"join-{tg_user_id}")
    join_msg = await tg.send_message(
        chat_id,
        join_prompt_text(),
        inline_keyboard([[url_button("Войти в группу", invite_link)]]),
    )
    db.set_join_message(settings.database_url, tg_user_id, join_msg["message_id"], invite_link, chat_id)


async def run_daily_check(tg: TelegramAPI, settings: Settings) -> dict:
    now_utc = db.utcnow()
    rows = db.subscriptions_for_daily_check(settings.database_url)
    result = {"checked": 0, "grace": 0, "expired": 0}

    for row in rows:
        result["checked"] += 1
        new_status = db.update_status_for_dates(settings.database_url, int(row["tg_user_id"]), now_utc)

        if new_status == "grace":
            result["grace"] += 1

        if new_status == "expired":
            result["expired"] += 1
            tg_user_id = int(row["tg_user_id"])
            try:
                await tg.ban_chat_member(settings.group_id, tg_user_id)
            except Exception:
                pass
            db.mark_removed_from_group(settings.database_url, tg_user_id)
            chat_id = int(row.get("last_chat_id") or tg_user_id)
            await tg.send_message(chat_id, start_text(), start_keyboard())

    return result
