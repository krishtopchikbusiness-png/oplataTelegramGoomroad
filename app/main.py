from __future__ import annotations

import asyncio
import logging
from datetime import time

from telegram.ext import ApplicationBuilder, CallbackQueryHandler, ChatJoinRequestHandler, CommandHandler

from app.config import load_settings
from app.db import Database
from app.handlers import callback_router, chatid_cmd, myid_cmd, on_join_request, start_cmd
from app.jobs import expire_subscriptions_job


logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def main() -> None:
    # =========================
    # 1. Грузим настройки из переменных Railway
    # =========================
    settings = load_settings()

    # =========================
    # 2. Подключаемся к базе
    # =========================
    db = Database(settings.database_url)
    await db.connect()

    # =========================
    # 3. Собираем Telegram-бота
    # =========================
    application = ApplicationBuilder().token(settings.bot_token).build()

    # Кладем настройки и базу внутрь application,
    # чтобы из хендлеров и задач к ним был доступ.
    application.bot_data["settings"] = settings
    application.bot_data["db"] = db

    # =========================
    # 4. Команды
    # =========================
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("myid", myid_cmd))
    application.add_handler(CommandHandler("chatid", chatid_cmd))

    # =========================
    # 5. Кнопки и заявки на вступление
    # =========================
    application.add_handler(CallbackQueryHandler(callback_router))
    application.add_handler(ChatJoinRequestHandler(on_join_request))

    # =========================
    # 6. Ежедневная проверка срока доступа
    #    Каждый день в 10:00 по Киеву
    # =========================
    application.job_queue.run_daily(
        callback=expire_subscriptions_job,
        time=time(hour=10, minute=0, tzinfo=settings.tz),
        name="expire_subscriptions_daily",
    )

    # =========================
    # 7. Запуск через polling
    # =========================
    logger.info("Бот запущен через polling")
    try:
        await application.initialize()
        await application.start()
        await application.updater.start_polling(drop_pending_updates=True)
        await asyncio.Event().wait()
    finally:
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        await db.close()


if __name__ == "__main__":
    asyncio.run(main())
