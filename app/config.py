import os
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from dotenv import load_dotenv


load_dotenv()


@dataclass(slots=True)
class Settings:
    bot_token: str
    admin_id: int
    group_id: int
    card_number: str
    card_holder: str
    database_url: str
    tz: ZoneInfo



def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    admin_id = os.getenv("ADMIN_ID", "").strip()
    group_id = os.getenv("GROUP_ID", "").strip()
    card_number = os.getenv("CARD_NUMBER", "").strip()
    card_holder = os.getenv("CARD_HOLDER", "").strip()
    database_url = os.getenv("DATABASE_URL", "").strip()
    tz_name = os.getenv("TZ", "Europe/Kyiv").strip() or "Europe/Kyiv"

    missing = []
    if not bot_token:
        missing.append("BOT_TOKEN")
    if not admin_id:
        missing.append("ADMIN_ID")
    if not group_id:
        missing.append("GROUP_ID")
    if not card_number:
        missing.append("CARD_NUMBER")
    if not database_url:
        missing.append("DATABASE_URL")

    if missing:
        raise RuntimeError(f"Не заполнены переменные: {', '.join(missing)}")

    return Settings(
        bot_token=bot_token,
        admin_id=int(admin_id),
        group_id=int(group_id),
        card_number=card_number,
        card_holder=card_holder,
        database_url=database_url,
        tz=ZoneInfo(tz_name),
    )
