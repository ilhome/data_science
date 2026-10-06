with source as (
    select * from {{ source('raw', 'sales') }}
)

select
    {{ surrogate_key(['order_id', 'product']) }} as sales_line_key,
    order_id,
    cast(order_date as date)                      as order_date,
    customer_id,
    product                                       as product_name,
    quantity,
    cast(unit_price as numeric(10, 2))            as unit_price,
    cast(total_amount as numeric(12, 2))          as total_amount,
    loaded_at
from source
