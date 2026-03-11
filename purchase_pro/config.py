from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    mysql_host: str
    mysql_port: int
    mysql_user: str
    mysql_password: str
    mysql_database: str
    product_url: str
    product_id: str
    poll_interval_seconds: int
    headless: bool
    name_selector: str
    price_selector: str
    availability_selector: str



def _require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value



def load_config() -> AppConfig:
    load_dotenv()

    return AppConfig(
        mysql_host=_require_env("MYSQL_HOST"),
        mysql_port=int(os.getenv("MYSQL_PORT", "3306")),
        mysql_user=_require_env("MYSQL_USER"),
        mysql_password=_require_env("MYSQL_PASSWORD"),
        mysql_database=_require_env("MYSQL_DATABASE"),
        product_url=_require_env("PRODUCT_URL"),
        product_id=_require_env("PRODUCT_ID"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "5")),
        headless=os.getenv("HEADLESS", "true").lower() == "true",
        name_selector=os.getenv("NAME_SELECTOR", "h1"),
        price_selector=os.getenv("PRICE_SELECTOR", "[class*='price']"),
        availability_selector=os.getenv("AVAILABILITY_SELECTOR", "button"),
    )
