CREATE TABLE IF NOT EXISTS sales_raw (
    order_id VARCHAR(50),
    order_date DATE,
    customer_id VARCHAR(50),
    product VARCHAR(100),
    quantity INTEGER,
    unit_price NUMERIC(10,2),
    total_amount NUMERIC(10,2)
);

CREATE TABLE IF NOT EXISTS daily_sales_metrics (
    order_date DATE,
    total_orders INTEGER,
    total_revenue NUMERIC(12,2),
    total_units INTEGER
);
