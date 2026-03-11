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
    poll_interval_seconds: int
    headless: bool
    category_tab_selector: str
    product_card_selector: str
    name_selector: str
    price_selector: str
    stock_selector: str



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
        product_url=os.getenv("PRODUCT_URL", "https://rtjgfsc.rtjzj.com/pages/tabBar/shop/shop"),
        poll_interval_seconds=int(os.getenv("POLL_INTERVAL_SECONDS", "5")),
        headless=os.getenv("HEADLESS", "true").lower() == "true",
        category_tab_selector=os.getenv("CATEGORY_TAB_SELECTOR", ".tab-item, .category-item"),
        product_card_selector=os.getenv("PRODUCT_CARD_SELECTOR", ".goods-item, .product-item, .item"),
        name_selector=os.getenv("NAME_SELECTOR", ".goods-name, .product-name, .title"),
        price_selector=os.getenv("PRICE_SELECTOR", ".price, .goods-price, [class*='price']"),
        stock_selector=os.getenv("STOCK_SELECTOR", ".stock, .inventory, [class*='stock'], [class*='inventory']"),
    )
