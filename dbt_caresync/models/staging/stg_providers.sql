select
    "Id"           as provider_id,
    "ORGANIZATION" as organization_id,
    "NAME"         as provider_name,
    "GENDER"       as gender,
    "SPECIALITY"   as speciality,
    "CITY"         as city,
    "STATE"        as state,
    "ZIP"          as zip,
    "ENCOUNTERS"   as lifetime_encounters,
    "PROCEDURES"   as lifetime_procedures,
    "NPI"          as npi,
    _run_id,
    _loaded_at
from {{ source('raw', 'providers') }}
