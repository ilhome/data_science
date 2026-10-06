select
    product_id,
    trim(product_name)                  as product_name,
    category,
    brand,
    cast(list_price as numeric(10, 2))  as list_price
from {{ ref('product_catalog') }}
