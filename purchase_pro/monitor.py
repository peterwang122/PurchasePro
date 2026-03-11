from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from playwright.sync_api import Page, sync_playwright

from .config import AppConfig
from .db import Database


@dataclass
class ProductState:
    product_key: str
    category_name: Optional[str]
    product_name: str
    price_raw: Optional[str]
    stock_count: int
    stock_raw: str
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
                    states = self._fetch_product_states(page)
                    self._persist_changes(states)
                    time.sleep(self._config.poll_interval_seconds)
            finally:
                browser.close()

    def _fetch_product_states(self, page: Page) -> list[ProductState]:
        page.goto(self._config.product_url, wait_until="networkidle", timeout=60000)

        all_states: list[ProductState] = []
        tab_locator = page.locator(self._config.category_tab_selector)
        tab_count = tab_locator.count()

        if tab_count == 0:
            all_states.extend(self._extract_cards(page, None))
            return all_states

        for index in range(tab_count):
            tab = tab_locator.nth(index)
            category_name = tab.inner_text().strip() or f"tab_{index}"
            tab.click()
            page.wait_for_timeout(600)
            all_states.extend(self._extract_cards(page, category_name))

        dedup: dict[str, ProductState] = {}
        for state in all_states:
            dedup[state.product_key] = state
        return list(dedup.values())

    def _extract_cards(self, page: Page, category_name: Optional[str]) -> list[ProductState]:
        states: list[ProductState] = []
        cards = page.locator(self._config.product_card_selector)

        for index in range(cards.count()):
            card = cards.nth(index)
            name = self._first_text_from(card, self._config.name_selector)
            if not name:
                continue

            stock_raw = self._first_text_from(card, self._config.stock_selector)
            stock_count = self._extract_int(stock_raw)
            if stock_count is None:
                continue

            price_raw = self._first_text_from(card, self._config.price_selector)
            product_key = f"{category_name or 'default'}::{name}"
            states.append(
                ProductState(
                    product_key=product_key,
                    category_name=category_name,
                    product_name=name,
                    price_raw=self._normalize_price(price_raw),
                    stock_count=stock_count,
                    stock_raw=stock_raw,
                    fetched_at=datetime.now(),
                )
            )
        return states

    def _persist_changes(self, states: list[ProductState]) -> None:
        if not states:
            print("未抓取到商品卡片，请检查选择器配置。")
            return

        for state in states:
            previous = self._db.get_last_stock_count(state.product_key)
            if previous == state.stock_count:
                print(f"[{state.fetched_at:%Y-%m-%d %H:%M:%S}] {state.product_name} 库存无变化: {state.stock_count}")
                continue

            snapshot_id = self._db.insert_snapshot(
                product_key=state.product_key,
                category_name=state.category_name,
                product_name=state.product_name,
                price_raw=state.price_raw,
                stock_count=state.stock_count,
                stock_raw=state.stock_raw,
                fetched_at=state.fetched_at,
            )
            self._db.insert_stock_event(
                product_key=state.product_key,
                previous_stock_count=previous,
                current_stock_count=state.stock_count,
                changed_at=state.fetched_at,
                snapshot_id=snapshot_id,
            )
            print(
                f"[{state.fetched_at:%Y-%m-%d %H:%M:%S}] {state.product_name} 库存变化: "
                f"{previous} -> {state.stock_count}, 价格: {state.price_raw or 'N/A'}"
            )

    @staticmethod
    def _first_text_from(scope, selector_candidates: str) -> Optional[str]:
        selectors = [item.strip() for item in selector_candidates.split(",") if item.strip()]
        for selector in selectors:
            loc = scope.locator(selector).first
            if loc.count() > 0:
                text = loc.inner_text(timeout=1000).strip()
                if text:
                    return text
        return None

    @staticmethod
    def _extract_int(raw_text: Optional[str]) -> Optional[int]:
        if not raw_text:
            return None
        match = re.search(r"(\d+)", raw_text)
        return int(match.group(1)) if match else None

    @staticmethod
    def _normalize_price(price_text: Optional[str]) -> Optional[str]:
        if not price_text:
            return None
        cleaned = price_text.replace(",", "")
        matches = re.findall(r"\d+(?:\.\d+)?", cleaned)
        return matches[0] if matches else price_text.strip()
