from __future__ import annotations

from datetime import datetime
from typing import Optional

import mysql.connector
from mysql.connector import MySQLConnection

from .config import AppConfig


class Database:
    def __init__(self, config: AppConfig) -> None:
        self._conn: MySQLConnection = mysql.connector.connect(
            host=config.mysql_host,
            port=config.mysql_port,
            user=config.mysql_user,
            password=config.mysql_password,
            database=config.mysql_database,
            autocommit=False,
        )

    def close(self) -> None:
        self._conn.close()

    def get_last_stock_count(self, product_key: str) -> Optional[int]:
        query = """
            SELECT stock_count
            FROM product_snapshots
            WHERE product_key = %s
            ORDER BY fetched_at DESC
            LIMIT 1
        """
        with self._conn.cursor() as cur:
            cur.execute(query, (product_key,))
            row = cur.fetchone()
        return int(row[0]) if row and row[0] is not None else None

    def insert_snapshot(
        self,
        *,
        product_key: str,
        category_name: Optional[str],
        product_name: str,
        price_raw: Optional[str],
        stock_count: int,
        stock_raw: str,
        fetched_at: datetime,
    ) -> int:
        query = """
            INSERT INTO product_snapshots
            (product_key, category_name, product_name, price_raw, stock_count, stock_raw, fetched_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with self._conn.cursor() as cur:
            cur.execute(
                query,
                (product_key, category_name, product_name, price_raw, stock_count, stock_raw, fetched_at),
            )
            snapshot_id = cur.lastrowid
        self._conn.commit()
        return int(snapshot_id)

    def insert_stock_event(
        self,
        *,
        product_key: str,
        previous_stock_count: Optional[int],
        current_stock_count: int,
        changed_at: datetime,
        snapshot_id: int,
    ) -> None:
        query = """
            INSERT INTO stock_events
            (product_key, previous_stock_count, current_stock_count, changed_at, snapshot_id)
            VALUES (%s, %s, %s, %s, %s)
        """
        with self._conn.cursor() as cur:
            cur.execute(
                query,
                (product_key, previous_stock_count, current_stock_count, changed_at, snapshot_id),
            )
        self._conn.commit()
