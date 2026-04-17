from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

import asyncpg

from app.texts import PLANS


@dataclass
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


@dataclass
class Subscription:
    tg_user_id: int
    tg_username: str | None
    tg_first_name: str | None
    plan_code: str
    plan_name: str
    amount_text: str
    status: str
    access_until: datetime
    in_chat: bool
    user_chat_id: int
    status_message_chat_id: int | None
    status_message_id: int | None
    join_message_chat_id: int | None
    join_message_id: int | None
    invite_link: str | None
    updated_at: datetime


class Database:
    def __init__(self, dsn: str):
        self.dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self.dsn, min_size=1, max_size=5)
        await self.init_schema()

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()
            self.pool = None

    async def init_schema(self) -> None:
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

                CREATE TABLE IF NOT EXISTS subscriptions (
                    tg_user_id BIGINT PRIMARY KEY,
                    tg_username TEXT,
                    tg_first_name TEXT,
                    plan_code TEXT NOT NULL,
                    plan_name TEXT NOT NULL,
                    amount_text TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'active',
                    access_until TIMESTAMPTZ NOT NULL,
                    in_chat BOOLEAN NOT NULL DEFAULT FALSE,
                    user_chat_id BIGINT NOT NULL,
                    status_message_chat_id BIGINT,
                    status_message_id BIGINT,
                    join_message_chat_id BIGINT,
                    join_message_id BIGINT,
                    invite_link TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
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
            request_id = await con.fetchval(
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
                plan["name"],
                plan["amount"],
                user_chat_id,
            )
        return int(request_id)

    async def get_pending_payment_request_by_user(self, tg_user_id: int) -> PaymentRequest | None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                """
                SELECT id, tg_user_id, tg_username, tg_first_name,
                       plan_code, plan_name, amount_text, user_chat_id,
                       status, admin_message_chat_id, admin_message_id, created_at
                FROM payment_requests
                WHERE tg_user_id = $1 AND status = 'pending'
                ORDER BY id DESC
                LIMIT 1;
                """,
                tg_user_id,
            )
        return PaymentRequest(**dict(row)) if row else None

    async def close_other_pending_requests_for_user(self, tg_user_id: int, keep_request_id: int) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE payment_requests
                SET status = 'confirmed',
                    reviewed_at = NOW()
                WHERE tg_user_id = $1
                  AND status = 'pending'
                  AND id <> $2;
                """,
                tg_user_id,
                keep_request_id,
            )


    async def set_payment_request_admin_message(
        self,
        request_id: int,
        chat_id: int,
        message_id: int,
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
                chat_id,
                message_id,
            )

    async def get_payment_request(self, request_id: int) -> PaymentRequest | None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                """
                SELECT id, tg_user_id, tg_username, tg_first_name,
                       plan_code, plan_name, amount_text, user_chat_id,
                       status, admin_message_chat_id, admin_message_id, created_at
                FROM payment_requests
                WHERE id = $1;
                """,
                request_id,
            )
        return PaymentRequest(**dict(row)) if row else None

    async def mark_payment_request(self, request_id: int, status: str) -> None:
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

    async def save_subscription(
        self,
        tg_user_id: int,
        tg_username: str | None,
        tg_first_name: str | None,
        plan_code: str,
        plan_name: str,
        amount_text: str,
        access_until: datetime,
        user_chat_id: int,
    ) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                INSERT INTO subscriptions (
                    tg_user_id, tg_username, tg_first_name,
                    plan_code, plan_name, amount_text,
                    status, access_until, in_chat, user_chat_id, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, 'active', $7, FALSE, $8, NOW())
                ON CONFLICT (tg_user_id) DO UPDATE SET
                    tg_username = EXCLUDED.tg_username,
                    tg_first_name = EXCLUDED.tg_first_name,
                    plan_code = EXCLUDED.plan_code,
                    plan_name = EXCLUDED.plan_name,
                    amount_text = EXCLUDED.amount_text,
                    status = 'active',
                    access_until = EXCLUDED.access_until,
                    user_chat_id = EXCLUDED.user_chat_id,
                    updated_at = NOW();
                """,
                tg_user_id,
                tg_username,
                tg_first_name,
                plan_code,
                plan_name,
                amount_text,
                access_until,
                user_chat_id,
            )

    async def get_subscription(self, tg_user_id: int) -> Subscription | None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            row = await con.fetchrow(
                """
                SELECT tg_user_id, tg_username, tg_first_name,
                       plan_code, plan_name, amount_text, status, access_until,
                       in_chat, user_chat_id, status_message_chat_id, status_message_id,
                       join_message_chat_id, join_message_id, invite_link, updated_at
                FROM subscriptions
                WHERE tg_user_id = $1;
                """,
                tg_user_id,
            )
        return Subscription(**dict(row)) if row else None

    async def set_status_message(self, tg_user_id: int, chat_id: int, message_id: int) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE subscriptions
                SET status_message_chat_id = $2,
                    status_message_id = $3,
                    updated_at = NOW()
                WHERE tg_user_id = $1;
                """,
                tg_user_id,
                chat_id,
                message_id,
            )

    async def set_join_message(self, tg_user_id: int, chat_id: int, message_id: int, invite_link: str) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE subscriptions
                SET join_message_chat_id = $2,
                    join_message_id = $3,
                    invite_link = $4,
                    updated_at = NOW()
                WHERE tg_user_id = $1;
                """,
                tg_user_id,
                chat_id,
                message_id,
                invite_link,
            )

    async def clear_join_message(self, tg_user_id: int) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE subscriptions
                SET join_message_chat_id = NULL,
                    join_message_id = NULL,
                    invite_link = NULL,
                    updated_at = NOW()
                WHERE tg_user_id = $1;
                """,
                tg_user_id,
            )

    async def set_in_chat(self, tg_user_id: int, in_chat: bool) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE subscriptions
                SET in_chat = $2,
                    updated_at = NOW()
                WHERE tg_user_id = $1;
                """,
                tg_user_id,
                in_chat,
            )

    async def mark_expired(self, tg_user_id: int) -> None:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            await con.execute(
                """
                UPDATE subscriptions
                SET status = 'expired',
                    in_chat = FALSE,
                    join_message_chat_id = NULL,
                    join_message_id = NULL,
                    invite_link = NULL,
                    updated_at = NOW()
                WHERE tg_user_id = $1;
                """,
                tg_user_id,
            )

    async def get_expired_active_subscriptions(self, now_dt: datetime) -> Sequence[Subscription]:
        assert self.pool is not None
        async with self.pool.acquire() as con:
            rows = await con.fetch(
                """
                SELECT tg_user_id, tg_username, tg_first_name,
                       plan_code, plan_name, amount_text, status, access_until,
                       in_chat, user_chat_id, status_message_chat_id, status_message_id,
                       join_message_chat_id, join_message_id, invite_link, updated_at
                FROM subscriptions
                WHERE status = 'active' AND access_until < $1;
                """,
                now_dt,
            )
        return [Subscription(**dict(row)) for row in rows]
