-- The modeled layer must account for every cent loaded into the raw layer.
with raw_total as (
    select round(sum(total_amount), 2) as revenue from {{ source('raw', 'sales') }}
),

fact_total as (
    select round(sum(total_amount), 2) as revenue from {{ ref('fct_sales') }}
),

report_total as (
    select round(sum(total_revenue), 2) as revenue from {{ ref('daily_sales_metrics') }}
)

select raw_total.revenue as raw_revenue,
       fact_total.revenue as fact_revenue,
       report_total.revenue as report_revenue
from raw_total, fact_total, report_total
where raw_total.revenue <> fact_total.revenue
   or fact_total.revenue <> report_total.revenue
