import unittest
from datetime import datetime

from purchase_pro.monitor import ProductMonitor, ProductState


class FakeDB:
    def __init__(self, previous=None):
        self.previous = previous or {}
        self.snapshots = []
        self.events = []

    def get_last_stock_count(self, product_key):
        return self.previous.get(product_key)

    def insert_snapshot(self, **kwargs):
        self.snapshots.append(kwargs)
        return len(self.snapshots)

    def insert_stock_event(self, **kwargs):
        self.events.append(kwargs)


class FakeConfig:
    headless = True
    poll_interval_seconds = 1


class MonitorTests(unittest.TestCase):
    def test_extract_int(self):
        self.assertEqual(ProductMonitor._extract_int("库存 25"), 25)
        self.assertEqual(ProductMonitor._extract_int("剩余:0件"), 0)
        self.assertIsNone(ProductMonitor._extract_int(None))

    def test_normalize_price(self):
        self.assertEqual(ProductMonitor._normalize_price("¥ 6,123.50"), "6123.50")
        self.assertEqual(ProductMonitor._normalize_price("未标价"), "未标价")
        self.assertIsNone(ProductMonitor._normalize_price(None))

    def test_persist_changes_only_on_stock_change(self):
        db = FakeDB(previous={"cat::A": 10})
        monitor = ProductMonitor(FakeConfig(), db)

        state_no_change = ProductState(
            product_key="cat::A",
            category_name="cat",
            product_name="A",
            price_raw="10.5",
            stock_count=10,
            stock_raw="库存10",
            fetched_at=datetime.now(),
        )
        state_changed = ProductState(
            product_key="cat::B",
            category_name="cat",
            product_name="B",
            price_raw="20.0",
            stock_count=5,
            stock_raw="库存5",
            fetched_at=datetime.now(),
        )

        monitor._persist_changes([state_no_change, state_changed])

        self.assertEqual(len(db.snapshots), 1)
        self.assertEqual(db.snapshots[0]["product_key"], "cat::B")
        self.assertEqual(db.snapshots[0]["price_raw"], "20.0")
        self.assertEqual(len(db.events), 1)
        self.assertEqual(db.events[0]["current_stock_count"], 5)


if __name__ == "__main__":
    unittest.main()
