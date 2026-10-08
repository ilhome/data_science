select
    customer_id,
    customer_segment,
    lifetime_orders,
    lifetime_revenue,
    avg_order_value,
    rank() over (order by lifetime_revenue desc) as revenue_rank
from {{ ref('dim_customers') }}
order by revenue_rank
limit 20
