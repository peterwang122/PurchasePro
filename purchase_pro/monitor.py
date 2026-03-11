from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, sync_playwright

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
        page.goto(self._config.product_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1500)

        all_states: list[ProductState] = []
        for category_name in self._config.category_names:
            self._click_category(page, category_name)
            page.wait_for_timeout(800)

            dom_states = self._extract_cards(page, category_name)
            if dom_states:
                all_states.extend(dom_states)
                continue

            json_states = self._extract_from_embedded_json(page, category_name)
            if json_states:
                all_states.extend(json_states)
                continue

            all_states.extend(self._extract_from_full_text(page, category_name))

        if not all_states:
            all_states.extend(self._extract_cards(page, "推荐分类"))
            all_states.extend(self._extract_from_embedded_json(page, "推荐分类"))
            all_states.extend(self._extract_from_full_text(page, "推荐分类"))

        dedup: dict[str, ProductState] = {}
        for state in all_states:
            dedup[state.product_key] = state
        return list(dedup.values())

    def _click_category(self, page: Page, category_name: str) -> None:
        by_text = page.get_by_text(category_name, exact=False)
        count = by_text.count()
        if count > 0:
            for i in range(min(count, 8)):
                loc = by_text.nth(i)
                try:
                    if loc.is_visible(timeout=300):
                        loc.click(timeout=1500)
                        return
                except PlaywrightTimeoutError:
                    continue
                except Exception:
                    continue

        tabs = page.locator(self._config.category_tab_selector)
        for i in range(min(tabs.count(), 30)):
            tab = tabs.nth(i)
            try:
                txt = tab.inner_text(timeout=300).strip()
                if category_name in txt or txt in category_name:
                    tab.click(timeout=1500)
                    return
            except Exception:
                continue

    def _extract_cards(self, page: Page, category_name: Optional[str]) -> list[ProductState]:
        states: list[ProductState] = []
        cards = page.locator(self._config.product_card_selector)

        for index in range(min(cards.count(), 300)):
            card = cards.nth(index)
            card_text = self._safe_text(card)
            if not card_text or len(card_text) < 2:
                continue

            name = self._first_text_from(card, self._config.name_selector) or self._guess_name(card_text)
            if not name:
                continue

            stock_raw = self._first_text_from(card, self._config.stock_selector) or self._find_stock_text(card_text)
            stock_count = self._extract_int(stock_raw)
            if stock_count is None:
                continue

            price_raw = self._first_text_from(card, self._config.price_selector) or self._find_price_text(card_text)
            fetched_at = datetime.now()
            product_key = f"{category_name or 'default'}::{name}"
            states.append(
                ProductState(
                    product_key=product_key,
                    category_name=category_name,
                    product_name=name,
                    price_raw=self._normalize_price(price_raw),
                    stock_count=stock_count,
                    stock_raw=stock_raw,
                    fetched_at=fetched_at,
                )
            )
        return states

    def _extract_from_embedded_json(self, page: Page, category_name: str) -> list[ProductState]:
        html = page.content()
        states: list[ProductState] = []

        for payload in re.findall(r"\{.*?\}", html, flags=re.S):
            if "库存" not in payload and "stock" not in payload.lower():
                continue
            try:
                data = json.loads(payload)
            except Exception:
                continue
            for item in self._walk_items(data):
                name = self._pick_text(item, ["goodsName", "productName", "name", "title"])
                stock_value = self._pick_text(item, ["stock", "stockNum", "inventory", "quantity"])
                if not name or stock_value is None:
                    continue
                stock_raw = f"库存{stock_value}"
                stock_count = self._extract_int(str(stock_value))
                if stock_count is None:
                    continue
                price_raw = self._pick_text(item, ["price", "salePrice", "currentPrice"])
                fetched_at = datetime.now()
                states.append(
                    ProductState(
                        product_key=f"{category_name}::{name}",
                        category_name=category_name,
                        product_name=name,
                        price_raw=self._normalize_price(str(price_raw) if price_raw is not None else None),
                        stock_count=stock_count,
                        stock_raw=stock_raw,
                        fetched_at=fetched_at,
                    )
                )
        return states

    def _extract_from_full_text(self, page: Page, category_name: str) -> list[ProductState]:
        full_text = page.inner_text("body")
        lines = [line.strip() for line in full_text.splitlines() if line.strip()]
        states: list[ProductState] = []

        for i, line in enumerate(lines):
            if not self._looks_like_product_name(line):
                continue
            stock_idx = self._find_next_stock_line_index(lines, i + 1)
            if stock_idx is None:
                continue

            stock_raw = lines[stock_idx]
            stock_count = self._extract_int(stock_raw)
            if stock_count is None:
                continue

            price_raw = self._find_product_price(lines, stock_idx + 1)
            fetched_at = datetime.now()
            states.append(
                ProductState(
                    product_key=f"{category_name}::{line}",
                    category_name=category_name,
                    product_name=line,
                    price_raw=price_raw,
                    stock_count=stock_count,
                    stock_raw=stock_raw,
                    fetched_at=fetched_at,
                )
            )

        return states

    def _persist_changes(self, states: list[ProductState]) -> None:
        if not states:
            print("未抓取到商品卡片或库存信息，请检查分类按钮和选择器配置。")
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
                f"[{state.fetched_at:%Y-%m-%d %H:%M:%S}] {state.category_name or '默认'} / {state.product_name} 库存变化: "
                f"{previous} -> {state.stock_count}, 价格: {state.price_raw or 'N/A'}"
            )

    @staticmethod
    def _first_text_from(scope: Any, selector_candidates: str) -> Optional[str]:
        selectors = [item.strip() for item in selector_candidates.split(",") if item.strip()]
        for selector in selectors:
            try:
                loc = scope.locator(selector).first
                if loc.count() > 0:
                    text = loc.inner_text(timeout=500).strip()
                    if text:
                        return text
            except Exception:
                continue
        return None

    @staticmethod
    def _safe_text(scope: Any) -> Optional[str]:
        try:
            text = scope.inner_text(timeout=300)
            return text.strip() if text else None
        except Exception:
            return None

    @staticmethod
    def _guess_name(card_text: str) -> Optional[str]:
        for line in [item.strip() for item in card_text.splitlines() if item.strip()]:
            if "库存" in line or "¥" in line or "$" in line:
                continue
            if re.search(r"\d+", line) and len(line) <= 3:
                continue
            return line
        return None

    @staticmethod
    def _find_stock_text(card_text: str) -> Optional[str]:
        m = re.search(r"(库存\s*[:：]?\s*\d+)", card_text)
        return m.group(1) if m else None

    @staticmethod
    def _find_price_text(card_text: str) -> Optional[str]:
        m = re.search(r"([¥￥]?\s*\d+(?:,\d{3})*(?:\.\d+)?)", card_text)
        return m.group(1) if m else None

    @staticmethod
    def _extract_int(raw_text: Optional[str]) -> Optional[int]:
        if not raw_text:
            return None
        match = re.search(r"(\d+)", str(raw_text))
        return int(match.group(1)) if match else None

    @staticmethod
    def _normalize_price(price_text: Optional[str]) -> Optional[str]:
        if not price_text:
            return None
        cleaned = str(price_text).replace(",", "")
        matches = re.findall(r"\d+(?:\.\d+)?", cleaned)
        return matches[-1] if matches else str(price_text).strip()

    @staticmethod
    def _looks_like_product_name(line: str) -> bool:
        return line.startswith("融通金") or "金条" in line or "银条" in line or "铂" in line

    @staticmethod
    def _find_next_stock_line_index(lines: list[str], start_idx: int) -> Optional[int]:
        for idx in range(start_idx, min(start_idx + 30, len(lines))):
            if re.search(r"库存\s*\d+", lines[idx]):
                return idx
        return None

    def _find_product_price(self, lines: list[str], start_idx: int) -> Optional[str]:
        candidates: list[float] = []
        for idx in range(start_idx, min(start_idx + 40, len(lines))):
            line = lines[idx]
            if self._looks_like_product_name(line):
                break
            for token in re.findall(r"\d+(?:\.\d+)?", line.replace(",", "")):
                try:
                    candidates.append(float(token))
                except ValueError:
                    continue
        if not candidates:
            return None
        return f"{max(candidates):.2f}"

    def _walk_items(self, data: Any) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []

        def _walk(node: Any) -> None:
            if isinstance(node, dict):
                if self._looks_like_product(node):
                    items.append(node)
                for value in node.values():
                    _walk(value)
            elif isinstance(node, list):
                for value in node:
                    _walk(value)

        _walk(data)
        return items

    @staticmethod
    def _looks_like_product(node: dict[str, Any]) -> bool:
        keys = {k.lower() for k in node.keys()}
        has_name = any(k in keys for k in ["goodsname", "productname", "name", "title"])
        has_stock = any(k in keys for k in ["stock", "stocknum", "inventory", "quantity"])
        return has_name and has_stock

    @staticmethod
    def _pick_text(node: dict[str, Any], keys: list[str]) -> Optional[str]:
        lowered = {k.lower(): v for k, v in node.items()}
        for key in keys:
            value = lowered.get(key.lower())
            if value is None:
                continue
            if isinstance(value, (int, float, str)):
                return str(value)
        return None
