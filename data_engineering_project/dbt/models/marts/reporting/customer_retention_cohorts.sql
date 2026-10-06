-- Monthly acquisition cohorts: what share of customers who first bought in a given
-- month came back to buy again N months later.
with customer_months as (
    select distinct
        sales.customer_key,
        date_trunc('month', customers.first_order_date)::date as cohort_month,
        date_trunc('month', sales.order_date)::date           as activity_month
    from {{ ref('fct_sales') }} as sales
    join {{ ref('dim_customers') }} as customers using (customer_key)
),

cohort_activity as (
    select
        cohort_month,
        (extract(year from age(activity_month, cohort_month)) * 12
            + extract(month from age(activity_month, cohort_month)))::int as months_since_first_order,
        count(*) as active_customers
    from customer_months
    group by 1, 2
)

select
    cohort_month,
    months_since_first_order,
    active_customers,
    first_value(active_customers) over (
        partition by cohort_month order by months_since_first_order
    ) as cohort_size,
    round(100.0 * active_customers / first_value(active_customers) over (
        partition by cohort_month order by months_since_first_order
    ), 2) as retention_pct
from cohort_activity
