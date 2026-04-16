from __future__ import annotations

from typing import Any

import httpx


class TelegramAPI:
    def __init__(self, token: str):
        self.base = f"https://api.telegram.org/bot{token}"

    async def call(self, method: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self.base}/{method}", json=payload or {})
            response.raise_for_status()
            data = response.json()
            if not data.get("ok"):
                raise RuntimeError(f"Telegram API error in {method}: {data}")
            return data["result"]

    async def send_message(self, chat_id: int, text: str, reply_markup: dict[str, Any] | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.call("sendMessage", payload)

    async def edit_message_text(
        self,
        chat_id: int,
        message_id: int,
        text: str,
        reply_markup: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "message_id": message_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self.call("editMessageText", payload)

    async def answer_callback(self, callback_query_id: str, text: str | None = None) -> None:
        payload: dict[str, Any] = {"callback_query_id": callback_query_id}
        if text:
            payload["text"] = text
        await self.call("answerCallbackQuery", payload)

    async def delete_message(self, chat_id: int, message_id: int) -> None:
        await self.call("deleteMessage", {"chat_id": chat_id, "message_id": message_id})

    async def set_webhook(self, url: str, secret_token: str) -> None:
        await self.call("setWebhook", {"url": url, "secret_token": secret_token, "drop_pending_updates": False})

    async def create_join_request_link(self, chat_id: int, name: str) -> str:
        result = await self.call(
            "createChatInviteLink",
            {
                "chat_id": chat_id,
                "name": name,
                "creates_join_request": True,
            },
        )
        return result["invite_link"]

    async def revoke_invite_link(self, chat_id: int, invite_link: str) -> None:
        await self.call("revokeChatInviteLink", {"chat_id": chat_id, "invite_link": invite_link})

    async def approve_join_request(self, chat_id: int, user_id: int) -> None:
        await self.call("approveChatJoinRequest", {"chat_id": chat_id, "user_id": user_id})

    async def decline_join_request(self, chat_id: int, user_id: int) -> None:
        await self.call("declineChatJoinRequest", {"chat_id": chat_id, "user_id": user_id})

    async def unban_chat_member(self, chat_id: int, user_id: int) -> None:
        await self.call("unbanChatMember", {"chat_id": chat_id, "user_id": user_id, "only_if_banned": True})

    async def ban_chat_member(self, chat_id: int, user_id: int) -> None:
        await self.call("banChatMember", {"chat_id": chat_id, "user_id": user_id})


def inline_keyboard(rows: list[list[dict[str, str]]]) -> dict[str, Any]:
    return {"inline_keyboard": rows}


def callback_button(text: str, data: str) -> dict[str, str]:
    return {"text": text, "callback_data": data}


def url_button(text: str, url: str) -> dict[str, str]:
    return {"text": text, "url": url}
