-- Runs once when the Postgres container is first created.

-- Metadata database for Airflow (kept separate from the warehouse).
CREATE DATABASE airflow;

-- Raw layer: written by the Python ETL, read by dbt sources.
CREATE SCHEMA IF NOT EXISTS raw;

CREATE TABLE IF NOT EXISTS raw.sales (
    order_id      VARCHAR(50)   NOT NULL,
    order_date    DATE          NOT NULL,
    customer_id   VARCHAR(50)   NOT NULL,
    product       VARCHAR(100)  NOT NULL,
    quantity      INTEGER       NOT NULL CHECK (quantity > 0),
    unit_price    NUMERIC(10,2) NOT NULL CHECK (unit_price >= 0),
    total_amount  NUMERIC(12,2) NOT NULL,
    loaded_at     TIMESTAMPTZ   NOT NULL,
    PRIMARY KEY (order_id, product)
);

-- Quarantine for rows that failed data quality rules (raw values kept as text).
CREATE TABLE IF NOT EXISTS raw.sales_rejected (
    order_id          TEXT,
    order_date        TEXT,
    customer_id       TEXT,
    product           TEXT,
    quantity          TEXT,
    unit_price        TEXT,
    rejection_reason  TEXT        NOT NULL,
    loaded_at         TIMESTAMPTZ NOT NULL
);

-- Modeled schemas (staging, marts, reporting) are created and managed by dbt.
