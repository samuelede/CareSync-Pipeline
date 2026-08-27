select
    "Id"          as organization_id,
    "NAME"        as organization_name,
    "ADDRESS"     as address,
    "CITY"        as city,
    "STATE"       as state,
    "ZIP"         as zip,
    "LAT"         as latitude,
    "LON"         as longitude,
    "PHONE"       as phone,
    "REVENUE"     as revenue,
    "UTILIZATION" as utilization,
    "NPI"         as npi,
    _run_id,
    _loaded_at
from {{ source('raw', 'organizations') }}
