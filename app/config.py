from __future__ import annotations

import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class Settings:
    bot_token: str
    admin_id: int
    group_id: int
    card_number: str
    card_holder: str
    channel_url: str
    database_url: str
    tz_name: str

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.tz_name)



def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value



def load_settings() -> Settings:
    return Settings(
        bot_token=_required("BOT_TOKEN"),
        admin_id=int(_required("ADMIN_ID")),
        group_id=int(_required("GROUP_ID")),
        card_number=_required("CARD_NUMBER"),
        card_holder=os.getenv("CARD_HOLDER", "").strip(),
        channel_url=_required("CHANNEL_URL"),
        database_url=_required("DATABASE_URL"),
        tz_name=os.getenv("TZ", "Europe/Kyiv").strip() or "Europe/Kyiv",
    )
