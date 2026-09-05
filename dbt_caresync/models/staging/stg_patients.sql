-- PHI-minimization boundary: SSN, DRIVERS, PASSPORT, FIRST, MIDDLE, LAST,
-- MAIDEN, PREFIX and SUFFIX are deliberately NOT selected. No downstream
-- model can re-expose them because they never cross this point. INCOME is
-- also excluded, personal income isn't a HIPAA identifier, but it's
-- unrelated to clinic/appointment reporting and there's no reason to
-- carry it further than RAW. FIPS is kept: it's the same granularity as
-- COUNTY, which is already selected below.
--
-- Dedup: patients is a full weekly snapshot, not an incremental delta, so
-- reloading the same run (or the same week twice) re-adds the same
-- patient IDs into RAW. QUALIFY keeps only the most recently loaded row
-- per Id, "latest wins", same as any standard SCD Type 1 dimension.
select
    "Id"                                          as patient_id,
    try_to_date("BIRTHDATE")                      as birthdate,
    try_to_date("DEATHDATE")                      as deathdate,
    upper(nullif(trim("MARITAL"), ''))             as marital_status,
    nullif(trim("RACE"), '')                      as race,
    nullif(trim("ETHNICITY"), '')                 as ethnicity,
    upper(nullif(trim("GENDER"), ''))              as gender,
    nullif(trim("CITY"), '')                      as city,
    nullif(trim("STATE"), '')                     as state,
    nullif(trim("COUNTY"), '')                    as county,
    nullif(trim("FIPS"), '')                      as fips,
    nullif(trim("ZIP"), '')                       as zip,
    try_to_number("HEALTHCARE_EXPENSES", 18, 2)   as healthcare_expenses,
    try_to_number("HEALTHCARE_COVERAGE", 18, 2)   as healthcare_coverage,
    _run_id,
    _loaded_at
from {{ source('raw', 'patients') }}
qualify row_number() over (partition by "Id" order by _loaded_at desc) = 1
