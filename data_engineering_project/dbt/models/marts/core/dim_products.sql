-- Products from the catalog, plus any product sold that the catalog does not know
-- about yet, so the fact table never loses rows on a missing dimension member.
with catalog as (
    select * from {{ ref('stg_product_catalog') }}
),

sold_but_unknown as (
    select distinct sales.product_name
    from {{ ref('stg_sales') }} as sales
    left join catalog using (product_name)
    where catalog.product_id is null
)

select
    {{ surrogate_key(['product_name']) }} as product_key,
    product_id,
    product_name,
    category,
    brand,
    list_price
from catalog

union all

select
    {{ surrogate_key(['product_name']) }} as product_key,
    null       as product_id,
    product_name,
    'Unknown'  as category,
    'Unknown'  as brand,
    null       as list_price
from sold_but_unknown
