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

    def get_last_availability(self, product_id: str) -> Optional[str]:
        query = """
            SELECT availability
            FROM product_snapshots
            WHERE product_id = %s
            ORDER BY fetched_at DESC
            LIMIT 1
        """
        with self._conn.cursor() as cur:
            cur.execute(query, (product_id,))
            row = cur.fetchone()
        return row[0] if row else None

    def insert_snapshot(
        self,
        *,
        product_url: str,
        product_id: str,
        product_name: Optional[str],
        price_raw: Optional[str],
        availability: str,
        html_hash: str,
        fetched_at: datetime,
    ) -> int:
        query = """
            INSERT INTO product_snapshots
            (product_url, product_id, product_name, price_raw, availability, html_hash, fetched_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        with self._conn.cursor() as cur:
            cur.execute(
                query,
                (
                    product_url,
                    product_id,
                    product_name,
                    price_raw,
                    availability,
                    html_hash,
                    fetched_at,
                ),
            )
            snapshot_id = cur.lastrowid
        self._conn.commit()
        return int(snapshot_id)

    def insert_stock_event(
        self,
        *,
        product_id: str,
        previous_availability: Optional[str],
        current_availability: str,
        changed_at: datetime,
        snapshot_id: int,
    ) -> None:
        query = """
            INSERT INTO stock_events
            (product_id, previous_availability, current_availability, changed_at, snapshot_id)
            VALUES (%s, %s, %s, %s, %s)
        """
        with self._conn.cursor() as cur:
            cur.execute(
                query,
                (
                    product_id,
                    previous_availability,
                    current_availability,
                    changed_at,
                    snapshot_id,
                ),
            )
        self._conn.commit()
