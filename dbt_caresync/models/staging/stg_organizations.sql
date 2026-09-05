select
    "Id"                                          as organization_id,
    nullif(trim("NAME"), '')                      as organization_name,
    nullif(trim("ADDRESS"), '')                   as address,
    nullif(trim("CITY"), '')                      as city,
    nullif(trim("STATE"), '')                     as state,
    nullif(trim("ZIP"), '')                       as zip,
    try_to_double("LAT")                          as latitude,
    try_to_double("LON")                          as longitude,
    nullif(trim("PHONE"), '')                     as phone,
    try_to_number("REVENUE", 18, 2)               as revenue,
    try_to_number("UTILIZATION")                  as utilization,
    nullif(trim("NPI"), '')                       as npi,
    _run_id,
    _loaded_at
from {{ source('raw', 'organizations') }}
qualify row_number() over (partition by "Id" order by _loaded_at desc) = 1
