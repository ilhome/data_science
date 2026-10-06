with orders as (
    select
        customer_id,
        order_id,
        min(order_date)   as order_date,
        sum(total_amount) as order_revenue
    from {{ ref('stg_sales') }}
    group by customer_id, order_id
),

customers as (
    select
        customer_id,
        min(order_date)          as first_order_date,
        max(order_date)          as last_order_date,
        count(*)                 as lifetime_orders,
        sum(order_revenue)       as lifetime_revenue
    from orders
    group by customer_id
)

select
    {{ surrogate_key(['customer_id']) }} as customer_key,
    customer_id,
    first_order_date,
    last_order_date,
    lifetime_orders,
    lifetime_revenue,
    round(lifetime_revenue / lifetime_orders, 2) as avg_order_value,
    case
        when lifetime_orders >= 10 or lifetime_revenue >= 10000 then 'VIP'
        when lifetime_orders >= 3 then 'Repeat'
        else 'One-time'
    end as customer_segment
from customers
