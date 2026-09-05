select
    "Id"                                          as provider_id,
    "ORGANIZATION"                                as organization_id,
    nullif(trim("NAME"), '')                      as provider_name,
    upper(nullif(trim("GENDER"), ''))              as gender,
    nullif(trim("SPECIALITY"), '')                as speciality,
    nullif(trim("CITY"), '')                      as city,
    nullif(trim("STATE"), '')                     as state,
    nullif(trim("ZIP"), '')                       as zip,
    try_to_number("ENCOUNTERS")                   as lifetime_encounters,
    try_to_number("PROCEDURES")                   as lifetime_procedures,
    nullif(trim("NPI"), '')                       as npi,
    _run_id,
    _loaded_at
from {{ source('raw', 'providers') }}
qualify row_number() over (partition by "Id" order by _loaded_at desc) = 1
