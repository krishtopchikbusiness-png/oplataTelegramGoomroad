from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app import db
from app.config import get_settings
from app.gumroad import (
    event_id_from_payload,
    event_type_from_payload,
    extract_telegram_id,
    parse_payment_time,
    plan_code_from_product_id,
)
from app.logic import (
    change_tariff_keyboard,
    render_home_for_user,
    render_plan_screen,
    resend_join_flow,
    run_daily_check,
    send_success_flow,
)
from app.telegram_api import TelegramAPI
from app.texts import change_tariff_text

load_dotenv()
settings = get_settings()
tg = TelegramAPI(settings.bot_token)


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_schema(settings.database_url)
    try:
        await tg.set_webhook(
            url=f"{settings.base_url.rstrip('/')}/telegram/webhook/{settings.telegram_webhook_secret}",
            secret_token=settings.telegram_webhook_secret,
        )
    except Exception:
        # На первом запуске BASE_URL иногда еще не готов.
        pass
    yield


app = FastAPI(title="Telegram Gumroad Group Bot", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/cron/check-subscriptions")
async def cron_check(request: Request):
    auth = request.headers.get("authorization", "")
    if auth != f"Bearer {settings.cron_secret}":
        raise HTTPException(status_code=401, detail="bad cron secret")
    result = await run_daily_check(tg, settings)
    return result


@app.post("/gumroad/ping")
async def gumroad_ping(request: Request):
    token = request.query_params.get("token")
    if token != settings.gumroad_ping_token:
        raise HTTPException(status_code=401, detail="bad gumroad token")

    form = await request.form()
    payload = {k: str(v) for k, v in form.items()}

    tg_user_id = extract_telegram_id(payload, settings.join_custom_field_name)
    if not tg_user_id:
        raise HTTPException(status_code=400, detail="telegram id not found in Gumroad payload")

    event_type = event_type_from_payload(payload)
    event_id = event_id_from_payload(payload)
    plan_code = plan_code_from_product_id(settings, payload.get("product_id"))

    if not plan_code:
        raise HTTPException(status_code=400, detail="unknown product_id; set GUMROAD_PRODUCT_ID_* correctly")

    is_new = db.record_payment_event(
        settings.database_url,
        event_id=event_id,
        event_type=event_type,
        payload=payload,
        tg_user_id=tg_user_id,
        subscription_id=payload.get("subscription_id") or payload.get("subscription_token") or payload.get("subscription"),
        plan_code=plan_code,
    )
    if not is_new:
        return {"ok": True, "duplicate": True}

    paid_at = parse_payment_time(payload)
    access_until = db.add_plan_period(paid_at, plan_code)
    next_billing_at = access_until
    grace_until = access_until + timedelta(days=2)

    existing = db.get_subscription(settings.database_url, tg_user_id)
    first_payment = not existing or existing.get("status") in {"expired", "cancelled"} or not existing.get("last_payment_at")

    db.upsert_subscription_from_payment(
        settings.database_url,
        tg_user_id=tg_user_id,
        chat_id=tg_user_id,
        username=existing.get("tg_username") if existing else None,
        first_name=existing.get("tg_first_name") if existing else None,
        plan_code=plan_code,
        payment_at=paid_at,
        access_until=access_until,
        next_billing_at=next_billing_at,
        grace_until=grace_until,
        gumroad_email=payload.get("email") or payload.get("purchase_email"),
        gumroad_customer_id=payload.get("purchaser_id") or payload.get("customer_id"),
        gumroad_subscription_id=payload.get("subscription_id") or payload.get("subscription_token") or payload.get("subscription"),
        gumroad_product_id=payload.get("product_id"),
    )

    await send_success_flow(tg, settings, tg_user_id, first_payment=first_payment)
    return {"ok": True}


@app.post("/telegram/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=401, detail="bad path secret")

    header_secret = request.headers.get("x-telegram-bot-api-secret-token")
    if header_secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=401, detail="bad header secret")

    update = await request.json()
    try:
        if "message" in update:
            await handle_message(update["message"])
        elif "callback_query" in update:
            await handle_callback(update["callback_query"])
        elif "chat_join_request" in update:
            await handle_join_request(update["chat_join_request"])
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=200)

    return {"ok": True}


async def handle_message(message: dict[str, Any]) -> None:
    text = str(message.get("text") or "").strip()
    chat_id = int(message["chat"]["id"])
    from_user = message["from"]
    tg_user_id = int(from_user["id"])

    db.upsert_user_profile(
        settings.database_url,
        tg_user_id=tg_user_id,
        chat_id=chat_id,
        username=from_user.get("username"),
        first_name=from_user.get("first_name"),
    )

    if text.startswith("/start"):
        await render_home_for_user(tg, settings, chat_id, None, tg_user_id)


async def handle_callback(callback: dict[str, Any]) -> None:
    data = str(callback.get("data") or "")
    callback_id = callback["id"]
    message = callback["message"]
    chat_id = int(message["chat"]["id"])
    message_id = int(message["message_id"])
    tg_user_id = int(callback["from"]["id"])

    if data == "home":
        await render_home_for_user(tg, settings, chat_id, message_id, tg_user_id)
        await tg.answer_callback(callback_id)
        return

    if data.startswith("plan:"):
        plan_code = data.split(":", 1)[1]
        await render_plan_screen(tg, settings, chat_id, message_id, tg_user_id, plan_code)
        await tg.answer_callback(callback_id)
        return

    if data == "change_tariff":
        await tg.edit_message_text(chat_id, message_id, change_tariff_text(), change_tariff_keyboard(settings))
        await tg.answer_callback(callback_id)
        return

    if data == "join":
        await resend_join_flow(tg, settings, tg_user_id)
        await tg.answer_callback(callback_id, "Ссылка на вход отправлена ниже")
        return

    await tg.answer_callback(callback_id)


async def handle_join_request(join_request: dict[str, Any]) -> None:
    tg_user_id = int(join_request["from"]["id"])
    sub = db.get_subscription(settings.database_url, tg_user_id)
    invite_link_obj = join_request.get("invite_link") or {}
    invite_link = invite_link_obj.get("invite_link")

    if not sub or sub.get("status") not in {"active", "grace"}:
        await tg.decline_join_request(settings.group_id, tg_user_id)
        return

    saved_link = sub.get("last_invite_link")
    if saved_link and invite_link and saved_link != invite_link:
        await tg.decline_join_request(settings.group_id, tg_user_id)
        return

    await tg.approve_join_request(settings.group_id, tg_user_id)
    db.mark_joined(settings.database_url, tg_user_id)

    if sub.get("join_message_id") and sub.get("last_chat_id"):
        try:
            await tg.delete_message(int(sub["last_chat_id"]), int(sub["join_message_id"]))
        except Exception:
            pass

    if saved_link:
        try:
            await tg.revoke_invite_link(settings.group_id, saved_link)
        except Exception:
            pass
    db.clear_join_message(settings.database_url, tg_user_id)
