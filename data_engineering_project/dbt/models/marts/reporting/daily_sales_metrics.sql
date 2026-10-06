with daily as (
    select
        dates.date_day,
        count(distinct sales.order_id)         as total_orders,
        count(distinct sales.customer_key)     as total_customers,
        coalesce(sum(sales.quantity), 0)       as total_units,
        coalesce(sum(sales.total_amount), 0)   as total_revenue,
        coalesce(sum(sales.discount_amount), 0) as total_discount
    from {{ ref('dim_date') }} as dates
    left join {{ ref('fct_sales') }} as sales on sales.date_key = dates.date_key
    group by dates.date_day
)

select
    date_day,
    total_orders,
    total_customers,
    total_units,
    total_revenue,
    total_discount,
    round(total_revenue / nullif(total_orders, 0), 2) as avg_order_value,
    round(avg(total_revenue) over (
        order by date_day rows between 6 preceding and current row
    ), 2) as revenue_7d_avg
from daily
