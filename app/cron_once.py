from __future__ import annotations

import asyncio

from dotenv import load_dotenv

from app.config import get_settings
from app.logic import run_daily_check
from app.telegram_api import TelegramAPI
from app import db


async def main() -> None:
    load_dotenv()
    settings = get_settings()
    db.init_schema(settings.database_url)
    tg = TelegramAPI(settings.bot_token)
    result = await run_daily_check(tg, settings)
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
