from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlencode

from app.config import Settings


def plan_code_from_product_id(settings: Settings, product_id: str | None) -> str | None:
    mapping = {
        settings.gumroad_product_id_1m: "1m",
        settings.gumroad_product_id_3m: "3m",
        settings.gumroad_product_id_12m: "12m",
    }
    return mapping.get(product_id or "")


def gumroad_url_for_plan(settings: Settings, plan_code: str, tg_user_id: int) -> str:
    base = {
        "1m": settings.gumroad_url_1m,
        "3m": settings.gumroad_url_3m,
        "12m": settings.gumroad_url_12m,
    }[plan_code]

    params = {
        "wanted": "true",
        settings.join_custom_field_name: str(tg_user_id),
    }
    separator = "&" if "?" in base else "?"
    return f"{base}{separator}{urlencode(params)}"


def extract_telegram_id(payload: dict[str, Any], field_name: str) -> int | None:
    candidates = [
        field_name,
        field_name.lower(),
        field_name.upper(),
        f"custom_fields[{field_name}]",
        f"custom_fields[{field_name.lower()}]",
        "Telegram ID",
        "telegram_id",
        "telegram id",
        "custom_fields[Telegram ID]",
        "custom_fields[telegram_id]",
    ]

    for key in candidates:
        value = payload.get(key)
        if value:
            try:
                return int(str(value).strip())
            except ValueError:
                continue

    for key, value in payload.items():
        key_l = str(key).lower()
        if "telegram" in key_l and "id" in key_l:
            try:
                return int(str(value).strip())
            except ValueError:
                continue
    return None


def parse_payment_time(payload: dict[str, Any]) -> datetime:
    # Ping payloads могут приходить без точного времени оплаты.
    # Для подписок нам достаточно текущего UTC времени как точки отсчета,
    # если точного timestamp нет.
    for key in ("sale_timestamp", "created_at", "paid_at"):
        raw = payload.get(key)
        if not raw:
            continue
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).astimezone(timezone.utc)
        except Exception:
            pass
    return datetime.now(timezone.utc)


def event_type_from_payload(payload: dict[str, Any]) -> str:
    return str(
        payload.get("event")
        or payload.get("type")
        or payload.get("sale_type")
        or payload.get("subscription_event")
        or "sale"
    )


def event_id_from_payload(payload: dict[str, Any]) -> str:
    return str(
        payload.get("event_id")
        or payload.get("sale_id")
        or payload.get("purchase_id")
        or payload.get("id")
        or payload.get("order_id")
        or f"fallback-{hash(frozenset((str(k), str(v)) for k, v in payload.items()))}"
    )
