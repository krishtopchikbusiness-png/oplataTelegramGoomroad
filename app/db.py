from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

import asyncpg

from app.texts import PLANS


@dataclass(slots=True)
class PaymentRequest:
    id: int
    tg_user_id: int
    tg_username: str | None
    tg_first_name: str | None
    plan_code: str
    plan_name: str
    amount_text: str
    user_chat_id: int
    status: str
    admin_message_chat_id: int | None
    admin_message_id: int | None
    created_at: datetime


@dataclass(slots=True)
class Subscription:
    tg_user_id: int
    tg_username: str | None
    tg_first_name: str | None
    plan_code: str
    plan_name: str
    access_until: datetime
    status: str
    is_in_group: bool
    last_chat_id: int | None
    status_message_id: int | None
    join_message_id: int | None
    last_invite_link: str | None


class Database:
    def __init__(self, dsn: str) -> None:
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)
        await self.init()

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def init(self) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_requests (
                    id BIGSERIAL PRIMARY KEY,
                    tg_user_id BIGINT NOT NULL,
                    tg_username TEXT,
                    tg_first_name TEXT,
                    plan_code TEXT NOT NULL,
                    plan_name TEXT NOT NULL,
                    amount_text TEXT NOT NULL,
                    user_chat_id BIGINT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    admin_message_chat_id BIGINT,
                    admin_message_id BIGINT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    reviewed_at TIMESTAMPTZ
                );
                """
            )
            await con.execute(
                """
                CREATE TABLE IF NOT EXISTS subscriptions (
                    tg_user_id BIGINT PRIMARY KEY,
                    tg_username TEXT,
                    tg_first_name TEXT,
                    plan_code TEXT NOT NULL,
                    plan_name TEXT NOT NULL,
                    access_until TIMESTAMPTZ NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    is_in_group BOOLEAN NOT NULL DEFAULT FALSE,
                    last_chat_id BIGINT,
                    status_message_id BIGINT,
                    join_message_id BIGINT,
                    last_invite_link TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                """
            )
            await con.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_subscriptions_status_access
                ON subscriptions (status, access_until);
                """
            )

    async def create_payment_request(
        self,
        tg_user_id: int,
        tg_username: str | None,
        tg_first_name: str | None,
        plan_code: str,
        user_chat_id: int,
    ) -> int:
        assert self.pool is not None
        plan = PLANS[plan_code]
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                """
                INSERT INTO payment_requests (
                    tg_user_id, tg_username, tg_first_name,
                    plan_code, plan_name, amount_text, user_chat_id
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                RETURNING id;
                """,
                tg_user_id,
                tg_username,
                tg_first_name,
                plan_code,
                plan["title"],
                plan["price"],
                user_chat_id,
            )
        return int(row["id"])

    async def set_payment_request_admin_message(
        self,
        request_id: int,
        admin_chat_id: int,
        admin_message_id: int,
    ) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE payment_requests
                SET admin_message_chat_id = $2,
                    admin_message_id = $3
                WHERE id = $1;
                """,
                request_id,
                admin_chat_id,
                admin_message_id,
            )

    async def get_payment_request(self, request_id: int) -> PaymentRequest | None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                "SELECT * FROM payment_requests WHERE id = $1;",
                request_id,
            )
        if not row:
            return None
        return PaymentRequest(**dict(row))

    async def update_payment_request_status(self, request_id: int, status: str) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE payment_requests
                SET status = $2,
                    reviewed_at = NOW()
                WHERE id = $1;
                """,
                request_id,
                status,
            )

    async def upsert_subscription(
        self,
        tg_user_id: int,
        tg_username: str | None,
        tg_first_name: str | None,
        plan_code: str,
        access_until: datetime,
        last_chat_id: int,
        status_message_id: int,
        join_message_id: int,
        invite_link: str,
    ) -> None:
        assert self.pool is not None
        plan = PLANS[plan_code]
        async with self.pool.acquire() as con:
            await con.execute(
                """
                INSERT INTO subscriptions (
                    tg_user_id, tg_username, tg_first_name, plan_code, plan_name,
                    access_until, status, is_in_group, last_chat_id,
                    status_message_id, join_message_id, last_invite_link,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5,
                    $6, 'active', FALSE, $7,
                    $8, $9, $10,
                    NOW(), NOW()
                )
                ON CONFLICT (tg_user_id)
                DO UPDATE SET
                    tg_username = EXCLUDED.tg_username,
                    tg_first_name = EXCLUDED.tg_first_name,
                    plan_code = EXCLUDED.plan_code,
                    plan_name = EXCLUDED.plan_name,
                    access_until = EXCLUDED.access_until,
                    status = 'active',
                    is_in_group = FALSE,
                    last_chat_id = EXCLUDED.last_chat_id,
                    status_message_id = EXCLUDED.status_message_id,
                    join_message_id = EXCLUDED.join_message_id,
                    last_invite_link = EXCLUDED.last_invite_link,
                    updated_at = NOW();
                """,
                tg_user_id,
                tg_username,
                tg_first_name,
                plan_code,
                plan["title"],
                access_until,
                last_chat_id,
                status_message_id,
                join_message_id,
                invite_link,
            )

    async def get_subscription(self, tg_user_id: int) -> Subscription | None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                "SELECT tg_user_id, tg_username, tg_first_name, plan_code, plan_name, access_until, status, is_in_group, last_chat_id, status_message_id, join_message_id, last_invite_link FROM subscriptions WHERE tg_user_id = $1;",
                tg_user_id,
            )
        if not row:
            return None
        return Subscription(**dict(row))

    async def mark_joined(self, tg_user_id: int) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE subscriptions
                SET is_in_group = TRUE,
                    join_message_id = NULL,
                    last_invite_link = NULL,
                    updated_at = NOW()
                WHERE tg_user_id = $1;
                """,
                tg_user_id,
            )

    async def expire_due_subscriptions(self, now_dt: datetime) -> list[Subscription]:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            rows = await con.fetch(
                """
                SELECT tg_user_id, tg_username, tg_first_name, plan_code, plan_name,
                       access_until, status, is_in_group, last_chat_id,
                       status_message_id, join_message_id, last_invite_link
                FROM subscriptions
                WHERE status = 'active' AND access_until < $1;
                """,
                now_dt,
            )
        return [Subscription(**dict(row)) for row in rows]

    async def mark_expired(self, tg_user_id: int) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE subscriptions
                SET status = 'expired',
                    is_in_group = FALSE,
                    join_message_id = NULL,
                    last_invite_link = NULL,
                    updated_at = NOW()
                WHERE tg_user_id = $1;
                """,
                tg_user_id,
            )

    async def clear_join_message(self, tg_user_id: int) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE subscriptions
                SET join_message_id = NULL,
                    last_invite_link = NULL,
                    updated_at = NOW()
                WHERE tg_user_id = $1;
                """,
                tg_user_id,
            )
