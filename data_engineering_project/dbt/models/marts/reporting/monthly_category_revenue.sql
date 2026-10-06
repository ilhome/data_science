with monthly as (
    select
        date_trunc('month', sales.order_date)::date as month,
        products.category,
        count(distinct sales.order_id)              as total_orders,
        sum(sales.quantity)                         as total_units,
        sum(sales.total_amount)                     as total_revenue
    from {{ ref('fct_sales') }} as sales
    join {{ ref('dim_products') }} as products using (product_key)
    group by 1, 2
)

select
    month,
    category,
    total_orders,
    total_units,
    total_revenue,
    round(100.0 * total_revenue / sum(total_revenue) over (partition by month), 2)
        as pct_of_month_revenue,
    round(100.0 * (total_revenue / nullif(lag(total_revenue) over (
        partition by category order by month
    ), 0) - 1), 2) as revenue_growth_mom_pct
from monthly
