CREATE DATABASE IF NOT EXISTS purchase_pro DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE purchase_pro;

CREATE TABLE IF NOT EXISTS product_snapshots (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_url VARCHAR(512) NOT NULL,
  product_id VARCHAR(64) NOT NULL,
  product_name VARCHAR(255) NULL,
  price_raw VARCHAR(128) NULL,
  availability VARCHAR(128) NULL,
  html_hash CHAR(64) NOT NULL,
  fetched_at DATETIME NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_product_time (product_id, fetched_at)
);

CREATE TABLE IF NOT EXISTS stock_events (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  product_id VARCHAR(64) NOT NULL,
  previous_availability VARCHAR(128) NULL,
  current_availability VARCHAR(128) NOT NULL,
  changed_at DATETIME NOT NULL,
  snapshot_id BIGINT NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT fk_stock_snapshot FOREIGN KEY (snapshot_id) REFERENCES product_snapshots(id),
  INDEX idx_product_change_time (product_id, changed_at)
);
