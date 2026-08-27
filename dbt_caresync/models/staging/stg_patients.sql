-- PHI-minimization boundary: SSN, DRIVERS, PASSPORT, FIRST, MIDDLE, LAST,
-- MAIDEN, PREFIX and SUFFIX are deliberately NOT selected. No downstream
-- model can re-expose them because they never cross this point. INCOME is
-- also excluded, personal income isn't a HIPAA identifier, but it's
-- unrelated to clinic/appointment reporting and there's no reason to
-- carry it further than RAW. FIPS is kept: it's the same granularity as
-- COUNTY, which is already selected below.
select
    "Id"                   as patient_id,
    "BIRTHDATE"             as birthdate,
    "DEATHDATE"             as deathdate,
    "MARITAL"                as marital_status,
    "RACE"                    as race,
    "ETHNICITY"                as ethnicity,
    "GENDER"                    as gender,
    "CITY"                        as city,
    "STATE"                        as state,
    "COUNTY"                        as county,
    "FIPS"                          as fips,
    "ZIP"                            as zip,
    "HEALTHCARE_EXPENSES"             as healthcare_expenses,
    "HEALTHCARE_COVERAGE"              as healthcare_coverage,
    _run_id,
    _loaded_at
from {{ source('raw', 'patients') }}
