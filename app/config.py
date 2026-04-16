import os
from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class Settings:
    bot_token: str
    database_url: str
    group_id: int
    base_url: str
    app_timezone: str
    telegram_webhook_secret: str
    cron_secret: str
    gumroad_ping_token: str
    gumroad_url_1m: str
    gumroad_url_3m: str
    gumroad_url_12m: str
    gumroad_product_id_1m: str
    gumroad_product_id_3m: str
    gumroad_product_id_12m: str
    join_custom_field_name: str
    gumroad_library_url: str

    @property
    def telegram_api_base(self) -> str:
        return f"https://api.telegram.org/bot{self.bot_token}"

    @property
    def host(self) -> str:
        return urlparse(self.base_url).netloc


def _require(name: str, default: str | None = None) -> str:
    value = os.getenv(name, default)
    if value is None or value == "":
        raise RuntimeError(f"Не задана переменная окружения: {name}")
    return value


def get_settings() -> Settings:
    return Settings(
        bot_token=_require("BOT_TOKEN"),
        database_url=_require("DATABASE_URL"),
        group_id=int(_require("GROUP_ID")),
        base_url=_require("BASE_URL"),
        app_timezone=os.getenv("APP_TIMEZONE", "Europe/Bucharest"),
        telegram_webhook_secret=_require("TELEGRAM_WEBHOOK_SECRET"),
        cron_secret=_require("CRON_SECRET"),
        gumroad_ping_token=_require("GUMROAD_PING_TOKEN"),
        gumroad_url_1m=_require("GUMROAD_URL_1M"),
        gumroad_url_3m=_require("GUMROAD_URL_3M"),
        gumroad_url_12m=_require("GUMROAD_URL_12M"),
        gumroad_product_id_1m=_require("GUMROAD_PRODUCT_ID_1M"),
        gumroad_product_id_3m=_require("GUMROAD_PRODUCT_ID_3M"),
        gumroad_product_id_12m=_require("GUMROAD_PRODUCT_ID_12M"),
        join_custom_field_name=os.getenv("GUMROAD_TG_FIELD_NAME", "Telegram ID"),
        gumroad_library_url=os.getenv("GUMROAD_LIBRARY_URL", "https://gumroad.com/library"),
    )
