from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row

from app.texts import PLAN_META


CREATE_SUBSCRIPTIONS_SQL = """
CREATE TABLE IF NOT EXISTS subscriptions (
    id BIGSERIAL PRIMARY KEY,
    tg_user_id BIGINT NOT NULL UNIQUE,
    tg_username TEXT,
    tg_first_name TEXT,
    plan_code TEXT NOT NULL CHECK (plan_code IN ('1m', '3m', '12m')),
    plan_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'grace', 'expired', 'cancelled')),
    started_at TIMESTAMPTZ,
    last_payment_at TIMESTAMPTZ,
    access_until TIMESTAMPTZ,
    next_billing_at TIMESTAMPTZ,
    grace_until TIMESTAMPTZ,
    is_in_group BOOLEAN NOT NULL DEFAULT FALSE,
    group_joined_at TIMESTAMPTZ,
    status_message_id BIGINT,
    join_message_id BIGINT,
    last_chat_id BIGINT,
    last_invite_link TEXT,
    invite_link_created_at TIMESTAMPTZ,
    gumroad_email TEXT,
    gumroad_customer_id TEXT,
    gumroad_subscription_id TEXT,
    gumroad_product_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_subscriptions_status ON subscriptions (status);
CREATE INDEX IF NOT EXISTS idx_subscriptions_next_billing_at ON subscriptions (next_billing_at);
CREATE INDEX IF NOT EXISTS idx_subscriptions_grace_until ON subscriptions (grace_until);
CREATE INDEX IF NOT EXISTS idx_subscriptions_gumroad_subscription_id ON subscriptions (gumroad_subscription_id);
"""

CREATE_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS payment_events (
    id BIGSERIAL PRIMARY KEY,
    provider TEXT NOT NULL DEFAULT 'gumroad',
    event_type TEXT NOT NULL,
    event_id TEXT NOT NULL UNIQUE,
    tg_user_id BIGINT,
    gumroad_subscription_id TEXT,
    plan_code TEXT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


@contextmanager
def get_conn(database_url: str):
    with psycopg.connect(database_url, row_factory=dict_row) as conn:
        yield conn


def init_schema(database_url: str) -> None:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_SUBSCRIPTIONS_SQL)
            cur.execute(CREATE_EVENTS_SQL)
        conn.commit()


def upsert_user_profile(database_url: str, tg_user_id: int, chat_id: int, username: str | None, first_name: str | None) -> None:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subscriptions (tg_user_id, tg_username, tg_first_name, plan_code, plan_name, status, last_chat_id)
                VALUES (%s, %s, %s, '1m', %s, 'expired', %s)
                ON CONFLICT (tg_user_id) DO UPDATE
                SET tg_username = EXCLUDED.tg_username,
                    tg_first_name = EXCLUDED.tg_first_name,
                    last_chat_id = EXCLUDED.last_chat_id,
                    updated_at = NOW()
                """,
                (tg_user_id, username, first_name, PLAN_META['1m']['title'], chat_id),
            )
        conn.commit()


def get_subscription(database_url: str, tg_user_id: int) -> dict[str, Any] | None:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM subscriptions WHERE tg_user_id = %s", (tg_user_id,))
            return cur.fetchone()


def set_status_message_id(database_url: str, tg_user_id: int, message_id: int, chat_id: int) -> None:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE subscriptions SET status_message_id = %s, last_chat_id = %s, updated_at = NOW() WHERE tg_user_id = %s",
                (message_id, chat_id, tg_user_id),
            )
        conn.commit()


def set_join_message(database_url: str, tg_user_id: int, message_id: int, invite_link: str, chat_id: int) -> None:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE subscriptions
                SET join_message_id = %s,
                    last_invite_link = %s,
                    invite_link_created_at = NOW(),
                    last_chat_id = %s,
                    updated_at = NOW()
                WHERE tg_user_id = %s
                """,
                (message_id, invite_link, chat_id, tg_user_id),
            )
        conn.commit()


def clear_join_message(database_url: str, tg_user_id: int) -> None:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE subscriptions
                SET join_message_id = NULL,
                    last_invite_link = NULL,
                    invite_link_created_at = NULL,
                    updated_at = NOW()
                WHERE tg_user_id = %s
                """,
                (tg_user_id,),
            )
        conn.commit()


def mark_joined(database_url: str, tg_user_id: int) -> None:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE subscriptions SET is_in_group = TRUE, group_joined_at = NOW(), updated_at = NOW() WHERE tg_user_id = %s",
                (tg_user_id,),
            )
        conn.commit()


def mark_removed_from_group(database_url: str, tg_user_id: int) -> None:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE subscriptions SET is_in_group = FALSE, updated_at = NOW() WHERE tg_user_id = %s",
                (tg_user_id,),
            )
        conn.commit()


def record_payment_event(
    database_url: str,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
    tg_user_id: int | None,
    subscription_id: str | None,
    plan_code: str | None,
) -> bool:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(
                    """
                    INSERT INTO payment_events (event_id, event_type, payload, tg_user_id, gumroad_subscription_id, plan_code)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (event_id, event_type, psycopg.types.json.Jsonb(payload), tg_user_id, subscription_id, plan_code),
                )
                conn.commit()
                return True
            except psycopg.errors.UniqueViolation:
                conn.rollback()
                return False


def upsert_subscription_from_payment(
    database_url: str,
    tg_user_id: int,
    chat_id: int | None,
    username: str | None,
    first_name: str | None,
    plan_code: str,
    payment_at: datetime,
    access_until: datetime,
    next_billing_at: datetime,
    grace_until: datetime,
    gumroad_email: str | None,
    gumroad_customer_id: str | None,
    gumroad_subscription_id: str | None,
    gumroad_product_id: str | None,
) -> None:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO subscriptions (
                    tg_user_id, tg_username, tg_first_name, plan_code, plan_name, status,
                    started_at, last_payment_at, access_until, next_billing_at, grace_until,
                    gumroad_email, gumroad_customer_id, gumroad_subscription_id, gumroad_product_id,
                    last_chat_id, updated_at
                )
                VALUES (%s, %s, %s, %s, %s, 'active', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (tg_user_id) DO UPDATE
                SET tg_username = COALESCE(EXCLUDED.tg_username, subscriptions.tg_username),
                    tg_first_name = COALESCE(EXCLUDED.tg_first_name, subscriptions.tg_first_name),
                    plan_code = EXCLUDED.plan_code,
                    plan_name = EXCLUDED.plan_name,
                    status = 'active',
                    started_at = COALESCE(subscriptions.started_at, EXCLUDED.started_at),
                    last_payment_at = EXCLUDED.last_payment_at,
                    access_until = EXCLUDED.access_until,
                    next_billing_at = EXCLUDED.next_billing_at,
                    grace_until = EXCLUDED.grace_until,
                    gumroad_email = COALESCE(EXCLUDED.gumroad_email, subscriptions.gumroad_email),
                    gumroad_customer_id = COALESCE(EXCLUDED.gumroad_customer_id, subscriptions.gumroad_customer_id),
                    gumroad_subscription_id = COALESCE(EXCLUDED.gumroad_subscription_id, subscriptions.gumroad_subscription_id),
                    gumroad_product_id = COALESCE(EXCLUDED.gumroad_product_id, subscriptions.gumroad_product_id),
                    last_chat_id = COALESCE(EXCLUDED.last_chat_id, subscriptions.last_chat_id),
                    updated_at = NOW()
                """,
                (
                    tg_user_id,
                    username,
                    first_name,
                    plan_code,
                    PLAN_META[plan_code]["title"],
                    payment_at,
                    payment_at,
                    access_until,
                    next_billing_at,
                    grace_until,
                    gumroad_email,
                    gumroad_customer_id,
                    gumroad_subscription_id,
                    gumroad_product_id,
                    chat_id,
                ),
            )
        conn.commit()


def set_status(database_url: str, tg_user_id: int, status: str) -> None:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE subscriptions SET status = %s, updated_at = NOW() WHERE tg_user_id = %s", (status, tg_user_id))
        conn.commit()


def subscriptions_for_daily_check(database_url: str) -> list[dict[str, Any]]:
    with get_conn(database_url) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM subscriptions
                WHERE status IN ('active', 'grace')
                ORDER BY tg_user_id ASC
                """
            )
            return cur.fetchall() or []


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def update_status_for_dates(database_url: str, tg_user_id: int, now_utc: datetime) -> str | None:
    row = get_subscription(database_url, tg_user_id)
    if not row:
        return None

    new_status = None
    if row["next_billing_at"] and now_utc > row["next_billing_at"] and row["status"] == "active":
        new_status = "grace"
    if row["grace_until"] and now_utc > row["grace_until"]:
        new_status = "expired"

    if new_status:
        set_status(database_url, tg_user_id, new_status)
    return new_status


def add_plan_period(base_date: datetime, plan_code: str) -> datetime:
    if plan_code == "1m":
        return base_date + timedelta(days=30)
    if plan_code == "3m":
        return base_date + timedelta(days=90)
    if plan_code == "12m":
        return base_date + timedelta(days=365)
    raise ValueError(f"Неизвестный тариф: {plan_code}")
