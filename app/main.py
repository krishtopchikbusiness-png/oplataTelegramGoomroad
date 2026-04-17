from __future__ import annotations

import logging

from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    CommandHandler,
)

from app.config import Settings, load_settings
from app.db import Database
from app.handlers import (
    admin_callback,
    chatid_command,
    join_request_handler,
    myid_command,
    pay_callback,
    plans_callback,
    restore_access_callback,
    start_command,
)
from app.jobs import schedule_jobs

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def post_init(application: Application) -> None:
    settings: Settings = application.bot_data["settings"]
    db: Database = application.bot_data["db"]
    await db.connect()
    schedule_jobs(application, settings)
    logger.info("Bot initialized")


async def post_shutdown(application: Application) -> None:
    db: Database = application.bot_data["db"]
    await db.close()
    logger.info("Bot shutdown complete")



def build_application() -> Application:
    settings = load_settings()
    db = Database(settings.database_url)

    app = (
        ApplicationBuilder()
        .token(settings.bot_token)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )
    app.bot_data["settings"] = settings
    app.bot_data["db"] = db

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("myid", myid_command))
    app.add_handler(CommandHandler("chatid", chatid_command))

    app.add_handler(CallbackQueryHandler(admin_callback, pattern=r"^admin:"))
    app.add_handler(CallbackQueryHandler(pay_callback, pattern=r"^pay:"))
    app.add_handler(CallbackQueryHandler(restore_access_callback, pattern=r"^restore:access$"))
    app.add_handler(CallbackQueryHandler(plans_callback, pattern=r"^(plan:|back:start$)"))

    app.add_handler(ChatJoinRequestHandler(join_request_handler))
    return app



def main() -> None:
    app = build_application()
    app.run_polling(allowed_updates=["message", "callback_query", "chat_join_request"])


if __name__ == "__main__":
    main()
