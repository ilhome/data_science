{{
    config(
        materialized='incremental',
        unique_key='sales_line_key',
        on_schema_change='append_new_columns'
    )
}}

-- One row per order line. Built incrementally: each run only reprocesses the most
-- recent days (with a lookback window for late-arriving and corrected records).
{% set lookback_days = var('fct_sales_lookback_days', 3) %}

with sales as (
    select * from {{ ref('stg_sales') }}
    {% if is_incremental() %}
    where order_date >= (
        select max(order_date) - {{ lookback_days }} from {{ this }}
    )
    {% endif %}
),

products as (
    select product_key, product_name, list_price from {{ ref('dim_products') }}
)

select
    sales.sales_line_key,
    sales.order_id,
    sales.order_date,
    cast(to_char(sales.order_date, 'YYYYMMDD') as integer)     as date_key,
    {{ surrogate_key(['sales.customer_id']) }}                 as customer_key,
    products.product_key,
    sales.quantity,
    sales.unit_price,
    products.list_price,
    round(coalesce(products.list_price - sales.unit_price, 0) * sales.quantity, 2)
                                                               as discount_amount,
    sales.total_amount,
    sales.loaded_at
from sales
left join products on sales.product_name = products.product_name
