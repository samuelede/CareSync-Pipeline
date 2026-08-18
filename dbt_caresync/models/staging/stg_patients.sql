-- PHI-minimization boundary: SSN, DRIVERS, PASSPORT, FIRST, LAST, MAIDEN,
-- PREFIX and SUFFIX are deliberately NOT selected. No downstream model can
-- re-expose them because they never cross this point.
select
    "Id"                     as patient_id,
    "BIRTHDATE"               as birthdate,
    "DEATHDATE"               as deathdate,
    "MARITAL"                 as marital_status,
    "RACE"                    as race,
    "ETHNICITY"                as ethnicity,
    "GENDER"                   as gender,
    "CITY"                      as city,
    "STATE"                      as state,
    "COUNTY"                      as county,
    "ZIP"                          as zip,
    "HEALTHCARE_EXPENSES"           as healthcare_expenses,
    "HEALTHCARE_COVERAGE"            as healthcare_coverage,
    _run_id,
    _loaded_at
from {{ source('raw', 'patients') }}
