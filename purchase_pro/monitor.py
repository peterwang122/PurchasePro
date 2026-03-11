from __future__ import annotations

import hashlib
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from playwright.sync_api import Browser, Page, sync_playwright

from .config import AppConfig
from .db import Database


OUT_OF_STOCK_KEYWORDS = ["无货", "售罄", "缺货", "补货中"]
IN_STOCK_KEYWORDS = ["立即购买", "加入购物车", "去结算", "有货", "马上抢"]


@dataclass
class ProductSnapshot:
    product_name: Optional[str]
    price_raw: Optional[str]
    availability: str
    html_hash: str
    fetched_at: datetime


class ProductMonitor:
    def __init__(self, config: AppConfig, db: Database) -> None:
        self._config = config
        self._db = db

    def run_forever(self) -> None:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self._config.headless)
            page = browser.new_page()
            try:
                while True:
                    snapshot = self._fetch_snapshot(page)
                    self._persist(snapshot)
                    time.sleep(self._config.poll_interval_seconds)
            finally:
                browser.close()

    def _fetch_snapshot(self, page: Page) -> ProductSnapshot:
        page.goto(self._config.product_url, wait_until="networkidle", timeout=60000)

        full_text = page.inner_text("body")
        product_name = self._first_text(page, self._config.name_selector)
        price_text = self._first_text(page, self._config.price_selector)
        availability_text = self._first_text(page, self._config.availability_selector)

        availability = self._resolve_availability(availability_text, full_text)
        html_hash = hashlib.sha256(full_text.encode("utf-8", errors="ignore")).hexdigest()

        return ProductSnapshot(
            product_name=product_name,
            price_raw=self._normalize_price(price_text),
            availability=availability,
            html_hash=html_hash,
            fetched_at=datetime.now(),
        )

    def _persist(self, snapshot: ProductSnapshot) -> None:
        previous_availability = self._db.get_last_availability(self._config.product_id)

        snapshot_id = self._db.insert_snapshot(
            product_url=self._config.product_url,
            product_id=self._config.product_id,
            product_name=snapshot.product_name,
            price_raw=snapshot.price_raw,
            availability=snapshot.availability,
            html_hash=snapshot.html_hash,
            fetched_at=snapshot.fetched_at,
        )

        if previous_availability != snapshot.availability:
            self._db.insert_stock_event(
                product_id=self._config.product_id,
                previous_availability=previous_availability,
                current_availability=snapshot.availability,
                changed_at=snapshot.fetched_at,
                snapshot_id=snapshot_id,
            )
            print(
                f"[{snapshot.fetched_at:%Y-%m-%d %H:%M:%S}] 库存状态变化: "
                f"{previous_availability} -> {snapshot.availability}"
            )
        else:
            print(
                f"[{snapshot.fetched_at:%Y-%m-%d %H:%M:%S}] 状态无变化: {snapshot.availability}; "
                f"价格: {snapshot.price_raw or 'N/A'}"
            )

    @staticmethod
    def _first_text(page: Page, selector_candidates: str) -> Optional[str]:
        selectors = [item.strip() for item in selector_candidates.split(",") if item.strip()]
        for selector in selectors:
            loc = page.locator(selector).first
            if loc.count() > 0:
                text = loc.inner_text(timeout=1000).strip()
                if text:
                    return text
        return None

    @staticmethod
    def _resolve_availability(availability_text: Optional[str], full_text: str) -> str:
        text = (availability_text or "") + "\n" + full_text
        for kw in OUT_OF_STOCK_KEYWORDS:
            if kw in text:
                return "OUT_OF_STOCK"
        for kw in IN_STOCK_KEYWORDS:
            if kw in text:
                return "IN_STOCK"
        return "UNKNOWN"

    @staticmethod
    def _normalize_price(price_text: Optional[str]) -> Optional[str]:
        if not price_text:
            return None
        matches = re.findall(r"\d+(?:\.\d+)?", price_text.replace(",", ""))
        return matches[0] if matches else price_text.strip()
